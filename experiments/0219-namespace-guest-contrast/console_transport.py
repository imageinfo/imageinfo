"""Bounded console phases on the ordinary runner's sole physical QMP channel."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import select
import stat
import threading
import time


INPUT_SECONDS = 60
MAX_INPUT = 1800
MAX_SCREEN = 16 * 1024 * 1024


class ConsoleError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ConsoleError(message)


def read_line(stream, deadline, *, clock=time.monotonic):
    # Use the raw descriptor throughout. A buffered readline can outlive the
    # absolute deadline when only a prefix is ready on the parent's pipe.
    line = bytearray()
    while b'\n' not in line:
        remaining = deadline - clock()
        require(remaining > 0 and len(line) < 512, 'parent instruction deadline or byte bound')
        ready, _, _ = select.select([stream], [], [], remaining)
        require(ready and clock() < deadline, 'parent instruction deadline')
        chunk = os.read(stream.fileno(), 512 - len(line))
        require(chunk, 'parent instruction stdin EOF')
        line.extend(chunk)
    require(clock() < deadline and line.endswith(b'\n') and line.count(b'\n') == 1,
            'exact single current-phase parent instruction required')
    return bytes(line)


class OwnedChannel:
    """Lock one complete physical exchange, including asynchronous reads."""

    def __init__(self, channel, *, clock=time.monotonic):
        self.channel = channel
        self.clock = clock
        self.lock = threading.Lock()
        self.endpoint = None
        self.refused = False
        self.restoration = threading.local()

    @contextmanager
    def cancellation(self):
        # Existing Controller.cancel is allowed one bounded restoration on an
        # unpoisoned channel. Its pre/post graphs and reopen are nine calls.
        # Tie the whole cleanup budget to the earlier of invocation or expiry.
        started = self.clock()
        expiry = self.endpoint.deadline if self.endpoint is not None else started
        self.restoration.deadline = min(started, expiry) + 9 * self.channel.timeout
        try:
            yield
        finally:
            del self.restoration.deadline

    def call(self, command, arguments=None, *, deadline=None, record=None, dispatch=None, acknowledge=None):
        started = self.clock()
        limit = started + self.channel.timeout
        if self.endpoint is not None:
            limit = min(limit, getattr(self.restoration, 'deadline', self.endpoint.deadline))
        if deadline is not None:
            limit = min(limit, deadline)
        remaining = limit - self.clock()
        if remaining <= 0 or not self.lock.acquire(timeout=remaining):
            self.refused = True
            raise ConsoleError('physical QMP lock or absolute call deadline')
        try:
            require(not self.refused and not self.channel.failed, 'refused or poisoned physical QMP channel')
            require(self.clock() < limit, 'physical QMP absolute call deadline')
            request_id = self.channel.sequence + 1
            if record is not None:
                record({'kind': 'qmp-request', 'id': request_id, 'command': command, 'arguments': arguments})
            require(not self.refused and self.clock() < limit, 'physical QMP absolute call deadline before dispatch')
            if dispatch is not None:
                dispatch()
            try:
                response = self.channel.call(command, arguments, deadline=limit)
            except BaseException:
                self.refused = True
                if record is not None:
                    record({'kind': 'qmp-reply-uncertain', 'id': request_id,
                            'dispatched': self.channel.sequence == request_id,
                            'poisoned': self.channel.failed})
                raise
            require(self.channel.sequence == request_id, 'physical QMP request sequence changed')
            if acknowledge is not None:
                acknowledge()
            if record is not None:
                record({'kind': 'qmp-reply', 'id': request_id, 'response': response})
            return response
        finally:
            self.lock.release()


def key(code, down):
    return {'type': 'key', 'data': {'key': {'type': 'qcode', 'data': code}, 'down': down}}


def chord(character):
    require(character.isascii() and (character.isalnum() or character in ' -./+='),
            'unsupported pinned console alphabet')
    code = {' ': 'spc', '-': 'minus', '.': 'dot', '/': 'slash', '+': 'equal', '=': 'equal'}.get(
        character, character.lower())
    codes = ['shift', code] if character.isupper() or character == '+' else [code]
    return [key(code, True) for code in codes] + [key(code, False) for code in reversed(codes)]


def fixed_keys(typed):
    require(type(typed) is str and 0 < len(typed) <= MAX_INPUT, 'pinned console command length')
    modifiers = ('shift', 'shift_r', 'ctrl', 'ctrl_r', 'alt', 'alt_r', 'meta_l', 'meta_r')
    return [[key(code, False) for code in modifiers], *(chord(character) for character in typed),
            [key('ret', True), key('ret', False)]]


def screen_digest(path, identity=None):
    path = Path(path)
    require(not path.is_symlink(), 'screen symlink refused')
    with path.open('rb') as stream:
        observed = os.fstat(stream.fileno())
        require(stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1
                and (identity is None or (observed.st_dev, observed.st_ino) == identity),
                'screen file identity changed')
        raw = stream.read(MAX_SCREEN + 1)
    require(0 < len(raw) <= MAX_SCREEN, 'missing, partial or oversized screen')
    # QMP's default screendump format is binary PPM with a fixed 8-bit depth.
    parts = raw.split(b'\n', 3)
    require(len(parts) == 4 and parts[0] == b'P6' and parts[2] == b'255', 'invalid QMP screen framing')
    geometry = parts[1].split()
    require(len(geometry) == 2 and all(v.isdigit() and 1 <= len(v) <= 5 for v in geometry),
            'invalid QMP screen geometry')
    width, height = map(int, geometry)
    require(width > 0 and height > 0 and width * height * 3 == len(parts[3]), 'partial QMP screen pixels')
    return hashlib.sha256(raw).hexdigest()


class ConsolePhase:
    def __init__(self, owner, endpoint, plan_cases, record, rules, *, clock=time.monotonic, sleep=time.sleep):
        self.owner, self.endpoint, self.cases, self.record = owner, endpoint, plan_cases, record
        self.rules = rules
        self.clock, self.sleep = clock, sleep
        self.deadline = endpoint.deadline
        self.phase = 'await-inspect'
        self.journaled = self.attempted = self.acknowledged = 0

    def dispatch(self, index):
        self.attempted = index

    def acknowledge(self, index):
        self.acknowledged = index

    @contextmanager
    def pre_input(self, phase, reserve=0):
        remaining = self.deadline - self.clock() - reserve
        require(remaining > 0 and self.endpoint.lock.acquire(timeout=remaining),
                'console state lock or original endpoint deadline')
        try:
            controller = self.endpoint.controller
            require(self.phase == phase and controller.state == 'prepared' and controller.session.sequence == 0
                    and not controller.session.refused and self.endpoint.failure is None
                    and not self.endpoint.stop.is_set() and self.endpoint.deadline == self.deadline
                    and self.clock() + reserve < self.deadline, 'console phase, prepared state or endpoint budget changed')
            yield
        finally:
            self.endpoint.lock.release()

    def query(self, name, args=None):
        return self.owner.call(name, args, deadline=self.deadline, record=self.record)

    def preflight(self):
        require(self.query('query-status')['running'] is True, 'guest is not running')
        values = self.query('query-named-block-nodes')
        nodes = {node['node-name']: node for node in values}
        require(len(nodes) == len(values), 'ambiguous current disk node')
        blocks = self.query('query-block')
        current = self.endpoint.controller
        for selected in self.cases:
            binding = selected['identities']['disk']
            raw, file = nodes[binding['raw_node']], nodes[binding['file_node']]
            require(raw['drv'] == 'raw' and raw['children'] == [{'node-name': binding['file_node'], 'child': 'file'}]
                    and file['drv'] == 'file' and file['image']['filename'] == binding['disk_path']
                    and file.get('children', []) == [], 'live direct disk graph changed or filter selected')
            matches = [entry for entry in blocks if entry.get('inserted', {}).get('node-name') == binding['raw_node']]
            base = '/machine/peripheral/' + binding['device_id']
            qdev = base + '/' + binding['device_id'] + '.0'
            require(len(matches) == 1 and matches[0]['qdev'] in (binding['device_id'], qdev, qdev + '/legacy[0]'),
                    'live attached device changed')
            require(self.query('qom-get', {'path': base, 'property': 'serial'}) == binding['device_serial'],
                    'live actual device serial changed')
            if binding['raw_node'] == current.binding.raw_node:
                filt = nodes[binding['filter_node']]
                require(filt['drv'] == 'blkdebug' and filt['children'] == [
                    {'node-name': binding['file_node'], 'child': 'image'}], 'prepared filter identity or child changed')
                self.rules(filt['image']['filename'], current.binding, current.rule)

    def inspect(self, screen, revalidate):
        with self.pre_input('await-inspect'):
            self.phase = 'inspecting'
            revalidate()
            self.preflight()
            # Reserve an exclusive name and verify the same inode after QMP
            # fills it. Any partial file stays in this new attempt directory.
            with Path(screen).open('xb') as stream:
                observed = os.fstat(stream.fileno())
            self.query('screendump', {'filename': str(screen)})
            sha = screen_digest(screen, (observed.st_dev, observed.st_ino))
            self.phase = 'await-launch'
            return sha

    def launch(self, revalidate, completed):
        with self.pre_input('await-launch', INPUT_SECONDS):
            self.phase = 'launch-consumed'
            revalidate(check_only=True)
            self.preflight()
            events = fixed_keys(revalidate())
            limit = self.clock() + INPUT_SECONDS
            require(limit < self.deadline, 'insufficient original endpoint budget for complete input')
            self.record({'kind': 'input-consumed', 'batches': len(events), 'deadline': limit})
            for index, batch in enumerate(events, 1):
                require(self.clock() < limit, 'input absolute deadline')
                # Journal before dispatch, so an unavailable ledger never
                # permits another unrecorded input event.
                self.record({'kind': 'input-dispatch', 'batch': index})
                self.journaled = index
                self.owner.call('input-send-event', {'events': batch}, deadline=limit, record=self.record,
                                dispatch=lambda: self.dispatch(index), acknowledge=lambda: self.acknowledge(index))
                if 1 < index < len(events):
                    self.sleep(.02)
            completed()
            self.phase = 'input-acknowledged'

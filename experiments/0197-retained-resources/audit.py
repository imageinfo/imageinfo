"""Audit one retained normal-full capture. No guest actions are performed."""
import argparse, hashlib, json, pathlib

def audit(path, worker=None):
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    assert not value.get('failed'), 'Startup/controller failure is not a worker result'
    assert value['exitCode']==0 and value['standardUser']
    assert value['volume']['FileSystem']=='NTFS' and value['volume']['FileSystemLabel']=='I197FULL'
    assert 100663296 <= value['volume']['Size'] <= 134217728
    assert not value['partition']['IsBoot'] and not value['partition']['IsSystem']
    if worker:assert hashlib.sha256(worker.read_bytes()).hexdigest()==value['workerSha256']
    lines=[line for line in value['stdout'].splitlines() if 'IMAGEINFO197 ' in line]
    assert len(lines)==1
    event=json.loads(lines[0].split('IMAGEINFO197 ',1)[1])
    assert event['schema']=='imageinfo-0197-full-v1' and event['windowsError']==112
    assert event['availableBefore'] > 64*1024*1024
    assert 0<=event['availableFull']<event['planCharge']-65536
    assert 0<event['fillerCompleteBytes']<128*1024*1024
    assert event['retainedCharge']==event['planCharge']*2
    assert event['attempts']==2 and event['constructorCalls']==0
    assert event['operationRootAbsent'] and not event['publicationPossible']
    assert event['sourceSha256']==hashlib.sha256(b'S'*4096).hexdigest()
    assert event['originalSha256']==hashlib.sha256(b'O'*4096).hexdigest()
    files={f['name']:f for f in value['files']}
    assert files['source.bin']['bytes']==files['original.bin']['bytes']==4096
    assert event['fillerCompleteBytes']<=files['bounded-fill197.bin']['bytes']<=128*1024*1024
    assert set(files)=={'source.bin','original.bin','fixture197.marker','bounded-fill197.bin'}
    return {'schema':'imageinfo-0197-audit-v1','passed':True,'event':event,'workerSha256':value['workerSha256'],'captureSha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=pathlib.Path);p.add_argument('--worker',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
    value=audit(a.capture,a.worker)
    if a.output:a.output.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'passed':True,'attempts':value['event']['attempts'],'constructorCalls':0}))
if __name__=='__main__':main()

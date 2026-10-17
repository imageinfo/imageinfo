"""One bounded normal-full guest cell; no fault injection or power operation."""
import argparse, hashlib, http.server, json, pathlib, sys, threading
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'0022-ordinary-output'))
from windows_guest import Qmp

def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);p.add_argument('worker',type=pathlib.Path);a=p.parse_args()
    root=a.root.resolve()
    if root!=pathlib.Path('/var/tmp/imageinfo-windows-eval-20261014/retained-resources-0197-20261017'):raise ValueError('Exact fresh fixture required')
    pre=json.loads((root/'preflight.private.json').read_text())
    disk=pathlib.Path(pre['disk']['path'])
    if disk.parent!=root or disk.stat().st_size!=134217728 or pre['hostDisksExposed'] or pre['sourceOriginalsExposed']:raise ValueError('Unsafe fixture')
    q=Qmp(root)
    try:
        q.call('blockdev-add',{'driver':'file','node-name':'i197file','filename':str(disk),'cache':{'direct':False,'no-flush':False}})
        q.call('blockdev-add',{'driver':'raw','node-name':'i197raw','file':'i197file'})
        q.call('device_add',{'driver':'usb-storage','id':'i197usb','drive':'i197raw','serial':'IMAGEINFO0197','write-cache':'on','rerror':'report','werror':'report'})
        (root/'block-binding.private.json').write_text(json.dumps(q.call('query-block'),indent=2))
    finally:q.close()
    worker=a.worker.read_bytes();script=pathlib.Path(__file__).with_name('guest.ps1').read_bytes()
    meta={'workerSha256':hashlib.sha256(worker).hexdigest(),'guestScriptSha256':hashlib.sha256(script).hexdigest(),'controllerSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
    (root/'worker-bindings.private.json').write_text(json.dumps(meta,indent=2))
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            data={'/worker.exe':worker,'/guest.ps1':script,'/meta':json.dumps(meta).encode()}.get(self.path)
            if data is None:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_POST(self):
            n=int(self.headers.get('Content-Length','0'))
            if self.path!='/result' or not 0<n<1048576:self.send_error(400);return
            value=json.loads(self.rfile.read(n));path=root/'result.private.json'
            if path.exists():self.send_error(409);return
            path.write_text(json.dumps(value,indent=2));self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')
    http.server.ThreadingHTTPServer(('0.0.0.0',18727),Handler).serve_forever()
if __name__=='__main__':main()

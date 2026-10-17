"""Read-only audit of the stopped #0197 image and its immutable backing chain."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess

def binding(path):
    st=path.stat();h=hashlib.sha256()
    with path.open('rb') as source:
        while chunk:=source.read(8*1024*1024):h.update(chunk)
    return {'path':str(path),'inode':st.st_ino,'device':st.st_dev,'bytes':st.st_size,'mtimeNs':st.st_mtime_ns,'sha256':h.hexdigest()}

def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);p.add_argument('--output-name',default='retained-audit.private');a=p.parse_args();root=a.root.resolve()
    assert root==pathlib.Path('/var/tmp/imageinfo-windows-eval-20261014/retained-resources-0197-20261017')
    assert a.output_name.endswith('.private') and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in a.output_name)
    for process in pathlib.Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name)==os.getpid():continue
        try:cmd=(process/'cmdline').read_bytes().split(b'\0')
        except OSError:continue
        if not cmd or not any(str(root).encode() in part for part in cmd):continue
        assert not (b'qemu-system-x86' in cmd[0] or b'swtpm' in cmd[0] or any(part.endswith(b'0197-retained-resources/controller.py') for part in cmd)), 'Guest/helpers must be stopped'
    assert not (root/'qemu.pid').exists()
    pre=json.loads((root/'preflight.private.json').read_text())
    immutable=[]
    for old in pre['immutableBindings']:
        now=binding(pathlib.Path(old['path']));assert now==old,'Backing image changed';immutable.append(now)
    out=root/a.output_name;out.mkdir()
    raw=pathlib.Path(pre['disk']['path']).resolve();assert raw.parent==root and raw.stat().st_size==134217728
    before=binding(raw);part=out/'fresh-full.ntfs'
    with raw.open('rb') as source,part.open('xb') as target:
        source.seek(1048576);shutil.copyfileobj(source,target,1048576)
    tools=root.parent/'native-errors-0048-tools/extracted';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(tools/'usr/lib/x86_64-linux-gnu')
    files={}
    for name,expected in [('source.bin',b'S'*4096),('original.bin',b'O'*4096),('fixture197.marker',b'imageinfo-0197-fresh-authored-128m-v1\n')]:
        result=subprocess.run([str(tools/'usr/bin/ntfscat'),str(part),'/'+name],capture_output=True,env=env,timeout=30)
        assert result.returncode==0 and result.stdout==expected
        files[name]={'bytes':len(expected),'sha256':hashlib.sha256(expected).hexdigest()}
    listing=subprocess.run([str(tools/'usr/bin/ntfsls'),'-l','-p','/',str(part)],capture_output=True,env=env,timeout=30)
    assert listing.returncode==0 and b'operation197' not in listing.stdout
    assert all(name.encode() in listing.stdout for name in [*files,'bounded-fill197.bin'])
    (out/'root-listing.private.log').write_bytes(listing.stdout+listing.stderr)
    assert binding(raw)==before
    value={'schema':'imageinfo-0197-offline-audit-v1','readOnlyOriginalImages':True,'guestAndHelpersStopped':True,'immutableBackingBindingsUnchanged':True,'immutableBindings':immutable,'retainedImage':before,'files':files,'operationRootAbsent':True,'profileAdmitted':False}
    (out/'audit.private.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'passed':True,'immutableBackingImages':len(immutable),'authoredFiles':len(files),'operationRootAbsent':True,'report':str(out/'audit.private.json')}))
if __name__=='__main__':main()

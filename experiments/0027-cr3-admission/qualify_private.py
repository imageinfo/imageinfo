"""Explicit private R5 derivative qualification; never run on unadmitted originals."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(1024*1024): digest.update(block)
    return digest.hexdigest()

def dump(path,value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def boxes(data,start=0,end=None):
    """Independent bounded box grammar; compressed samples are never searched."""
    end=len(data) if end is None else end
    result=[];position=start
    while position<end:
        assert end-position>=8
        size,kind=struct.unpack_from('>I4s',data,position);header=8
        if size==1:
            size=struct.unpack_from('>Q',data,position+8)[0];header=16
        elif size==0:size=end-position
        assert size>=header and position+size<=end
        result.append((kind,position+header,position+size))
        position+=size
    return result

def entries(data,base):
    order='<' if data[base:base+2]==b'II' else '>'
    assert data[base:base+2] in [b'II',b'MM'] and struct.unpack_from(order+'H',data,base+2)[0]==42
    directory=struct.unpack_from(order+'I',data,base+4)[0]
    count=struct.unpack_from(order+'H',data,base+directory)[0]
    assert count<=4096
    return [(struct.unpack_from(order+'H',data,base+directory+2+i*12)[0],base+directory+2+i*12) for i in range(count)],order

def metadata_blocks(data):
    result={}
    canon=bytes.fromhex('85c0b687820f11e08111f4ce462b6a48')
    for kind,start,end in boxes(data):
        if kind!=b'moov':continue
        for child,at,finish in boxes(data,start,end):
            if child==b'uuid' and data[at:at+16]==canon:
                for name,body,limit in boxes(data,at+16,finish):
                    if name in [b'CMT1',b'CMT2',b'CMT3',b'CMT4']:result[name]=(body,limit)
    assert len(result)==4
    return result

def field(data,kind,tag):
    base,_=metadata_blocks(data)[kind]
    table,order=entries(data,base)
    matching=[at for identifier,at in table if identifier==tag];assert len(matching)==1
    at=matching[0];dtype,count,value=struct.unpack_from(order+'HII',data,at+2)
    widths={1:1,2:1,3:2,4:4,5:8,7:1}
    length=widths[dtype]*count
    offset=at+8 if length<=4 else base+value
    assert offset+length<=metadata_blocks(data)[kind][1]
    return base,at,offset,length,order

def atom(kind,body):return struct.pack('>I4s',len(body)+8,kind)+body

def execute(root,name,argv,path,records,env=None):
    before=(sha(path),path.stat().st_mtime_ns)
    begin=datetime.datetime.now(datetime.timezone.utc).isoformat()
    proc=subprocess.run([str(arg) for arg in argv],capture_output=True,timeout=120,env=env)
    finish=datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert before==(sha(path),path.stat().st_mtime_ns),'Input changed'
    (root/(name+'.stdout')).write_bytes(proc.stdout);(root/(name+'.stderr')).write_bytes(proc.stderr)
    record={'id':name,'argv':[str(arg) for arg in argv],'startedAt':begin,'finishedAt':finish,'exitCode':proc.returncode,
            'inputSha256Before':before[0],'inputSha256After':sha(path),'inputMtimeUnchanged':True,
            'stdoutSha256':sha(root/(name+'.stdout')),'stderrSha256':sha(root/(name+'.stderr'))}
    records.append(record);dump(root/'runs.private.json',records)
    return proc

def run(manifest_path,root_path,public_path):
    if not __debug__:raise RuntimeError('Qualification requires Python without -O')
    manifest=json.loads(Path(manifest_path).read_text())
    root=Path(root_path).resolve()
    assert root.is_dir() and not root.is_symlink() and not list(root.iterdir()),'Explicit new private root required'
    assert manifest['permissionBasis'] and len(manifest['sources'])==8
    for tool in ['native','candidate','perl','reference','decoder']:
        assert sha(manifest[tool]['path'])==manifest[tool]['sha256'],'Tool identity changed'
    dump(root/'admission.private.json',manifest)
    records=[];results=[];artifacts=[]
    perl=Path(manifest['perl']['path']);ref=Path(manifest['reference']['path'])
    env={key:os.environ[key] for key in ['SYSTEMROOT','WINDIR','TEMP','TMP'] if key in os.environ}
    env.update(PATH=str(perl.parent)+os.pathsep+str(Path(os.environ['SYSTEMROOT'])/'System32'),
               PERL5LIB=manifest['perlLibrary'],LC_ALL='C',LANG='C',TZ='UTC0')
    dump(root/'environment.private.json',env)
    for source in manifest['sources']:
        path=Path(source['path']);assert sha(path)==source['sha256']
        original=(sha(path),path.stat().st_mtime_ns);data=path.read_bytes();fid=source['id']
        base,at,date_offset,date_length,order=field(data,b'CMT2',0x9003)
        assert date_length==20 and data[date_offset+19]==0
        cases=[('baseline',path,'OPAQUE_DEPENDENCY_UNPROVEN',None)]
        # All derivatives are separately named, new files in the admitted private
        # root. No original, old clone, output or recovery record is overwritten.
        modifications=[]
        uuid=bytes.fromhex('d8fec3d61b0e483c92975828877ec481')
        modifications.append(('c2pa',data+atom(b'uuid',uuid+b'\0\0\0\0update\0authored-indicator-only'),'KNOWN_AUTHENTICITY_STRUCTURE','C2PA_BMFF_UUID'))
        modifications.append(('unknown-uuid',data+atom(b'uuid',b'\x27'*16+b'opaque authored block'),'OPAQUE_DEPENDENCY_UNPROVEN',None))
        alias=bytearray(data);_,digitized,_,_,_=field(data,b'CMT2',0x9004)
        struct.pack_into(order+'HII',alias,digitized+2,2,20,date_offset-base)
        modifications.append(('alias',bytes(alias),'FIELD_ALLOCATION_ALIAS',None))
        tagged=bytearray(data);struct.pack_into(order+'H',tagged,digitized,0xcd41)
        modifications.append(('tiff-c2pa',bytes(tagged),'KNOWN_AUTHENTICITY_STRUCTURE','C2PA_TIFF_TAG'))
        cmt3,_=metadata_blocks(data)[b'CMT3'];table,canon_order=entries(data,cmt3)
        spot=next(address for tag,address in table if tag not in [1,7,16,0x4018,0x83])
        indicator=bytearray(data);struct.pack_into(canon_order+'HHII',indicator,spot,0x83,4,1,0)
        modifications.append(('canon-indicator',bytes(indicator),'KNOWN_AUTHENTICITY_STRUCTURE','CANON_ORIGINAL_DECISION_INDICATOR'))
        for name,content,expected,known in modifications:
            target=root/(fid+'-'+name+'.cr3')
            with target.open('xb') as output:output.write(content)
            artifacts.append({'id':fid+'-'+name,'path':str(target),'sha256':sha(target),'sourceId':fid,'recipe':name,
                              'basis':'Admitted camera clone plus authored structural/header derivative; private analysis only, no cryptographic-validity claim'})
            cases.append((name,target,expected,known))
        alias_path=root/(fid+'-alias.cr3');candidate=root/(fid+'-alias.candidate.cr3')
        p=execute(root,fid+'-candidate',[manifest['candidate']['path'],'stage',alias_path,candidate],alias_path,records)
        assert p.returncode==0 and json.loads(p.stdout)['published'] is False
        cases.append(('alias-candidate',candidate,'FIELD_ALLOCATION_ALIAS',None))
        artifacts.append({'id':fid+'-alias-candidate','path':str(candidate),'sha256':sha(candidate),'sourceId':fid,
                          'recipe':'#0021 fixed date on alias derivative','basis':'Private candidate demonstrates coupled decoded alias effect; never published'})
        # Independent full-file complement and box grammar check on that candidate.
        before_alias=alias_path.read_bytes();after_alias=candidate.read_bytes()
        assert len(before_alias)==len(after_alias)
        assert before_alias[:date_offset]==after_alias[:date_offset] and before_alias[date_offset+20:]==after_alias[date_offset+20:]
        assert after_alias[date_offset:date_offset+20]==b'2001:02:03 04:05:06\0'
        boxes(after_alias)
        oracle=[]
        for name,case_path,expected,known in cases:
            p=execute(root,fid+'-'+name+'-native',[manifest['native']['path'],'inspect',case_path,'2000:02:29 23:59:59'],case_path,records)
            assert p.returncode==0,p.stderr
            result=json.loads(p.stdout)
            assert not result['productionMutationAllowed'] and not result['artifactsCreated'] and result['fieldShapeVerified']
            assert expected in [r['code'] for r in result['refusals']],result
            if known:assert known in [r['code'] for r in result['knownStructures']]
            results.append({'id':fid+'-'+name,'expectedRefusal':expected,'knownIndicator':known,
                            'fieldShapeVerified':True,'productionMutationAllowed':False})
            p=execute(root,fid+'-'+name+'-reference',[perl,'-I',ref.parent/'lib',ref,'-config','','-j','-G1','-s',
                      '-DateTimeOriginal','-CreateDate','-OffsetTimeOriginal','-SubSecTimeOriginal','-CanonFirmwareVersion',
                      '-OriginalDecisionDataOffset','--',case_path],case_path,records,env)
            assert p.returncode==0
            parsed=json.loads(p.stdout);assert len(parsed)==1
            if name in ['alias','alias-candidate']:oracle.append(parsed[0])
        assert len(oracle)==2
        for observed in oracle:
            assert observed['ExifIFD:DateTimeOriginal']==observed['ExifIFD:CreateDate']
        assert oracle[1]['ExifIFD:DateTimeOriginal']=='2001:02:03 04:05:06'
        # The source reference date/offset/subsecond are preserved separately.
        for key in ['ExifIFD:OffsetTimeOriginal','ExifIFD:SubSecTimeOriginal']:
            assert oracle[0].get(key)==oracle[1].get(key)
        p=execute(root,fid+'-alias-unpack',[manifest['decoder']['path'],candidate],candidate,records)
        assert p.returncode==0 and not p.stderr and b'Unpacked' in p.stdout
        decoded=Path(str(candidate)+'.pgm');assert decoded.is_file()
        assert sha(decoded)==sha(Path(source['baselineDecoded']))
        artifacts.append({'id':fid+'-alias-unpack','path':str(decoded),'sha256':sha(decoded),'sourceId':fid,
                          'recipe':'Unprocessed LibRaw Bayer unpack','basis':'Private independent decoded derivative; no rendering/public distribution'})
        assert original==(sha(path),path.stat().st_mtime_ns)
        dump(root/'artifacts.private.json',artifacts)
        print(json.dumps({'fixtureId':fid,'nativeCases':len(cases),'sourceUnchanged':True,'decodedPairEqual':True}),flush=True)
    summary={'schemaVersion':1,'observedOn':'2026-10-12','sourceCount':8,'nativeCases':len(results),
             'independentReferenceReads':56,'privateCandidateRuns':8,'independentUnpacks':8,
             'decodedPairsEqual':8,'runCount':len(records),'authoredNegativeDerivatives':40,'candidateAliasDerivatives':8,
             'originalSourcesUnchanged':True,'sourceClonesUnchanged':True,'allMutationAdmissionsRefused':True,
             'cryptographicallySignedFixtures':0,'generalAuthenticityAbsenceEstablished':False,
             'productionMutationAllowed':False,'cases':results}
    dump(root/'summary.private.json',summary);dump(public_path,summary)
    retained={str(p.relative_to(root)):sha(p) for p in root.iterdir() if p.is_file()}
    dump(root/'capture-manifest.private.json',retained)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--root',required=True)
    parser.add_argument('--public',required=True)
    args=parser.parse_args();print(json.dumps(run(args.manifest,args.root,args.public),indent=2))

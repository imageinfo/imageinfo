# Independent read-only retained-artifact observer for #0175. No actor imports.
param(
    [Parameter(Mandatory=$true)][string]$CellDirectory,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($CellDirectory)
$out = [IO.Path]::GetFullPath($Destination)
if (-not [IO.Directory]::Exists($root)) { throw 'CELL_DIRECTORY_REQUIRED' }
if ($out.Equals($root,[StringComparison]::OrdinalIgnoreCase) -or
    $out.StartsWith($root.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'DESTINATION_MUST_BE_OUTSIDE_CELL'
}
if ([IO.File]::Exists($out)) { throw 'FRESH_DESTINATION_REQUIRED' }
# Refuse reparse points in the full resolved source/destination ancestry, before
# any enumeration or destination creation. Lexical normalization alone cannot
# make a junction destination outside the protected cell.
foreach ($candidatePath in @($root, [IO.Path]::GetDirectoryName($out))) {
    $ancestorPath = $candidatePath
    while ($ancestorPath) {
        if (([IO.File]::GetAttributes($ancestorPath) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'REPARSE_ANCESTRY_REFUSED' }
        $ancestorPath = [IO.Path]::GetDirectoryName($ancestorPath.TrimEnd('\','/'))
    }
}
# Only the destination diagnostic is created. Every source handle is OPEN_EXISTING
# with read/control access and all sharing; no flush, attribute/security setter,
# delete, rename, repair, imported authority or process/VM operation is available.
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.ComponentModel;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Microsoft.Win32.SafeHandles;
public static class Storage175Reader {
 [StructLayout(LayoutKind.Sequential)] struct Info {
  public uint Attributes,CreationLow,CreationHigh,AccessLow,AccessHigh,WriteLow,WriteHigh,
    Volume,SizeHigh,SizeLow,Links,IndexHigh,IndexLow;
 }
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern SafeFileHandle CreateFileW(string p,uint a,uint s,IntPtr sec,uint disp,uint flags,IntPtr t);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetFileInformationByHandle(SafeFileHandle h,out Info i);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetFileInformationByHandleEx(SafeFileHandle h,int cls,byte[] b,uint n);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadFile(SafeFileHandle h,byte[] b,uint n,out uint got,IntPtr o);
 [DllImport("advapi32.dll",SetLastError=true)] static extern uint GetSecurityInfo(SafeFileHandle h,int kind,uint flags,IntPtr owner,IntPtr group,IntPtr dacl,IntPtr sacl,out IntPtr sd);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool ConvertSecurityDescriptorToStringSecurityDescriptorW(IntPtr sd,uint rev,uint flags,out IntPtr text,out uint n);
 [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr p);
 static void Check(bool ok) { if(!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }
 static ulong Join(uint hi,uint lo) { return ((ulong)hi<<32)|lo; }
 static string Hex(byte[] b) { return BitConverter.ToString(b).Replace("-","").ToLowerInvariant(); }
 static string Security(SafeFileHandle h) {
  IntPtr sd; uint err=GetSecurityInfo(h,1,5,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,out sd);
  if(err!=0) throw new Win32Exception((int)err);
  try { IntPtr text; uint n; Check(ConvertSecurityDescriptorToStringSecurityDescriptorW(sd,1,5,out text,out n));
   try { if(n==0||n>32768) throw new IOException("SECURITY_BOUND"); return Marshal.PtrToStringUni(text); }
   finally { LocalFree(text); }
  } finally { LocalFree(sd); }
 }
 static string[] Streams(SafeFileHandle h,bool directory) {
  byte[] b=new byte[65536];
  if(!GetFileInformationByHandleEx(h,7,b,(uint)b.Length)) {
   int e=Marshal.GetLastWin32Error(); if(directory&&e==38) return new string[0]; throw new Win32Exception(e);
  }
  List<string> names=new List<string>(); int at=0;
  while(true) {
   if(at<0||at>b.Length-24||names.Count>=16) throw new IOException("STREAM_BOUND");
   uint next=BitConverter.ToUInt32(b,at), n=BitConverter.ToUInt32(b,at+4);
   if(n==0||n%2!=0||n>512||at+24+n>b.Length) throw new IOException("STREAM_NAME_BOUND");
   names.Add(Encoding.Unicode.GetString(b,at+24,(int)n));
   if(next==0) break; if(next<24+n||next%8!=0||next>b.Length-at-24) throw new IOException("STREAM_OFFSET_BOUND"); at+=(int)next;
  }
  return names.ToArray();
 }
 public static Dictionary<string,object> Observe(string path,bool directory) {
  using(var h=CreateFileW(path,0x80020000,7,IntPtr.Zero,3,0x02200000,IntPtr.Zero)) {
   if(h.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
   Info before,after; Check(GetFileInformationByHandle(h,out before));
   if((before.Attributes&0x400)!=0 || ((before.Attributes&16)!=0)!=directory) throw new IOException("OBJECT_KIND_OR_REPARSE");
   string sec=Security(h); string[] streams=Streams(h,directory);
   byte[] data=null;
   if(!directory) {
    if(Join(before.SizeHigh,before.SizeLow)>65536) throw new IOException("ARTIFACT_BOUND");
    byte[] buffer=new byte[65537]; uint n,total=0;
    while(total<buffer.Length) { byte[] part=new byte[buffer.Length-total]; Check(ReadFile(h,part,(uint)part.Length,out n,IntPtr.Zero)); if(n==0) break; Array.Copy(part,0,buffer,total,n); total+=n; }
    if(total>65536||total!=Join(before.SizeHigh,before.SizeLow)) throw new IOException("CONTENT_BOUND_OR_RACE");
    data=new byte[total]; Array.Copy(buffer,data,total);
   }
   Check(GetFileInformationByHandle(h,out after));
   // Last-access is observer affected and deliberately not a stable property.
   if(before.Volume!=after.Volume||before.IndexHigh!=after.IndexHigh||before.IndexLow!=after.IndexLow||before.SizeHigh!=after.SizeHigh||before.SizeLow!=after.SizeLow||before.Links!=after.Links||before.Attributes!=after.Attributes||before.CreationLow!=after.CreationLow||before.CreationHigh!=after.CreationHigh||before.WriteLow!=after.WriteLow||before.WriteHigh!=after.WriteHigh||sec!=Security(h)) throw new IOException("OBSERVATION_RACE");
   var r=new Dictionary<string,object>();
   r["volume"]= (ulong)before.Volume; r["file_index"]=Join(before.IndexHigh,before.IndexLow);
   r["size"]=Join(before.SizeHigh,before.SizeLow); r["links"]=(ulong)before.Links;
   r["attributes"]=(ulong)before.Attributes; r["creation_time"]=Join(before.CreationHigh,before.CreationLow); r["last_write_time"]=Join(before.WriteHigh,before.WriteLow);
   r["owner_dacl"]=sec; r["streams"]=streams; r["directory"]=directory;
   if(data!=null) { r["content_base64"]=Convert.ToBase64String(data); using(var sha=SHA256.Create()) r["sha256"]=Hex(sha.ComputeHash(data)); }
   return r;
  }
 }
}
'@
$files = @()
$errors = @()
$names = @('source.bin')
$unit = Join-Path $root 'unit'
if ([IO.Directory]::Exists($unit)) {
    if (([IO.File]::GetAttributes($unit) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'REPARSE_UNIT_REFUSED' }
    $children = @([IO.Directory]::EnumerateFileSystemEntries($unit))
    if ($children.Count -gt 6) { throw 'NAMESPACE_BOUND' }
    foreach ($p in ($children | Sort-Object)) { $names += ('unit/' + [IO.Path]::GetFileName($p)) }
}
foreach ($name in $names) {
    try {
        $row = [Storage175Reader]::Observe((Join-Path $root $name), $false)
        $row['path'] = $name
        $files += $row
    } catch { $errors += @{path=$name; error=$_.Exception.ToString()} }
}
$directories = @{}
foreach ($pair in @(@('parent',$root), @('root',$unit))) {
    if ([IO.Directory]::Exists($pair[1])) {
        try { $directories[$pair[0]] = [Storage175Reader]::Observe($pair[1], $true) }
        catch { $errors += @{path=$pair[0]; error=$_.Exception.ToString()} }
    }
}
$os = Get-CimInstance Win32_OperatingSystem
$snapshot = @{
    schema='imageinfo-0175-independent-snapshot-v1'; files=@($files); directories=$directories;
    errors=@($errors); observed_utc=[DateTime]::UtcNow.ToString('o');
    boot_utc=$os.LastBootUpTime.ToUniversalTime().ToString('o');
    os_build=$os.BuildNumber; os_version=$os.Version;
    read_only=$true; authority='none'; cell_directory=$root
}
$json = $snapshot | ConvertTo-Json -Depth 15 -Compress
$encoding = New-Object Text.UTF8Encoding($false)
$bytes = $encoding.GetBytes($json + "`n")
$stream = [IO.File]::Open($out,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
Write-Output 'IMAGEINFO175_INDEPENDENT_SNAPSHOT_COMPLETE'

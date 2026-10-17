#!/usr/bin/perl
# Fixed, read-only installed-file verifier; never receives media paths.
use strict;
use warnings;
use Digest::SHA;
use JSON::PP;
binmode STDIN;
binmode STDOUT;
my $input = '';
while (length($input) <= 1048576) {
    my $count = read(STDIN, my $block, 8192);
    defined($count) or die "stdin read failed\n";
    last if $count == 0;
    $input .= $block;
}
length($input) <= 1048576 or die "request bound\n";
my $request = JSON::PP->new->utf8->decode($input);
ref($request) eq 'HASH' && keys(%$request) == 1 && ref($request->{paths}) eq 'ARRAY'
    or die "request shape\n";
my @paths = @{$request->{paths}};
@paths > 0 && @paths <= 4096 or die "path count bound\n";
for my $index (0 .. $#paths) {
    my $path = $paths[$index];
    !ref($path) && defined($path) && $path !~ /[\x00\r\n]/ &&
        $path !~ m{(?:^|/)\.\.(?:/|$)} &&
        $path =~ m{^/(?:usr/|etc/|lib/|lib64/|mnt/c/Projects/imageinfo/\.local/tools/exiftool-13\.59-source/)}
        or die "installed path shape\n";
    open my $file, '<', $path or die "installed open failed\n";
    binmode $file;
    my $sha = Digest::SHA->new(256);
    $sha->addfile($file);
    my $size = -s $file;
    defined($size) or die "installed size failed\n";
    close($file) or die "installed close failed\n";
    print "$index\t", $sha->hexdigest, "\t$size\n" or die "stdout write failed\n";
}

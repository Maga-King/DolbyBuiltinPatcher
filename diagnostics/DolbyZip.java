import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

/** Offline ZIP helper embedded as DEX in the single diagnostic shell file. */
public final class DolbyZip {
    private static long total;
    private static int count;
    private static void add(Path root, Path dir, ZipOutputStream zip) throws IOException {
        List<Path> paths=new ArrayList<>();
        try (DirectoryStream<Path> stream=Files.newDirectoryStream(dir)) {
            for(Path path:stream) paths.add(path);
        }
        paths.sort(Comparator.comparing(Path::toString));
        for(Path path:paths) {
            if(Files.isSymbolicLink(path)) throw new IOException("Unexpected symlink: "+path);
            if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS)) {add(root,path,zip);continue;}
            if(!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)) throw new IOException("Not a regular file");
            if(++count>1400) throw new IOException("File count exceeded");
            String name=root.relativize(path).toString().replace(File.separatorChar,'/');
            zip.putNextEntry(new ZipEntry(name));
            try(InputStream in=Files.newInputStream(path)) {
                byte[] buffer=new byte[65536];int n;
                while((n=in.read(buffer))!=-1) {
                    total+=n;if(total>224L*1024*1024) throw new IOException("ZIP input limit exceeded");
                    zip.write(buffer,0,n);
                }
            }
            zip.closeEntry();
        }
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=2) throw new IllegalArgumentException("input-dir output.zip");
        Path root=Paths.get(args[0]).toRealPath(), output=Paths.get(args[1]).toAbsolutePath().normalize();
        if(output.startsWith(root)) throw new IOException("Output inside input");
        try(ZipOutputStream zip=new ZipOutputStream(new BufferedOutputStream(Files.newOutputStream(output,StandardOpenOption.CREATE_NEW)))) {
            zip.setLevel(1);add(root,root,zip);
        }
        // Read and verify each entry, not just the central directory.
        try(ZipFile zip=new ZipFile(output.toFile())) {
            Enumeration<? extends ZipEntry> entries=zip.entries();byte[] buffer=new byte[65536];
            while(entries.hasMoreElements()) {
                ZipEntry entry=entries.nextElement();CRC32 crc=new CRC32();long size=0;
                try(InputStream in=zip.getInputStream(entry)) {int n;while((n=in.read(buffer))!=-1){crc.update(buffer,0,n);size+=n;}}
                if(crc.getValue()!=entry.getCrc() || size!=entry.getSize()) throw new IOException("ZIP verification failed");
            }
        }
    }
}

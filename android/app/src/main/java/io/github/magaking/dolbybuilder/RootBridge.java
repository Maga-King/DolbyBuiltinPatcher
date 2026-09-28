package io.github.magaking.dolbybuilder;

import android.content.Context;
import android.os.Build;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Only called by our packaged Python adapter; never exposed as an exported service. */
public final class RootBridge {
    public interface Logger { void log(String message); }
    private final Context context;
    private final Logger logger;
    private final AtomicBoolean cancelled = new AtomicBoolean();
    private volatile Process current;
    public RootBridge(Context context, Logger logger) { this.context=context; this.logger=logger; }
    public void log(String message) { logger.log(message); }
    public String model() { return Build.MANUFACTURER + " " + Build.MODEL; }
    public boolean isCancelled() { return cancelled.get(); }
    public void cancel() { cancelled.set(true); Process p=current; if (p!=null) p.destroy(); }
    public String exec(String script, int timeout) throws Exception {
        File output=File.createTempFile("root-out-", ".txt", context.getCacheDir());
        try { run(script, timeout, output); return new String(Files.readAllBytes(output.toPath()), StandardCharsets.UTF_8); }
        finally { output.delete(); }
    }
    public void execToFile(String script, int timeout, String output) throws Exception {
        File target=new File(output).getCanonicalFile();
        String allowed=context.getFilesDir().getCanonicalPath()+File.separator;
        if (!target.getPath().startsWith(allowed)) throw new IOException("拒绝写入 App 私有目录之外");
        run(script,timeout,target);
    }
    private void run(String script, int timeout, File output) throws Exception {
        if (cancelled.get()) throw new IOException("已取消");
        File error=File.createTempFile("root-err-", ".txt", context.getCacheDir());
        Process process=null;
        try {
            // Redirection is opened by the app, so cached files remain app-owned.
            process=new ProcessBuilder("su","-c","/system/bin/sh")
                    .redirectOutput(output).redirectError(error).start();
            current=process;
            try (OutputStream stdin=process.getOutputStream()) { stdin.write(script.getBytes(StandardCharsets.UTF_8)); }
            if (!process.waitFor(Math.min(600,Math.max(1,timeout)),TimeUnit.SECONDS)) {
                process.destroy(); throw new IOException("root 读取超时，未修改系统");
            }
            if (cancelled.get()) throw new IOException("已取消");
            if (process.exitValue()!=0) {
                String detail=new String(Files.readAllBytes(error.toPath()),StandardCharsets.UTF_8);
                throw new IOException("root 命令失败 ("+process.exitValue()+"): "+detail.substring(Math.max(0,detail.length()-1800)));
            }
        } finally { current=null; if (process!=null && process.isAlive()) process.destroy(); error.delete(); }
    }
}

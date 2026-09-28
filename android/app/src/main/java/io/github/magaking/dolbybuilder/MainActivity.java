package io.github.magaking.dolbybuilder;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowManager;
import android.widget.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import java.io.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int SAVE=21;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView status,logs;
    private Button generate,root,save,cancel;
    private ProgressBar progress;
    private volatile boolean busy=false;
    private volatile RootBridge bridge;
    private File lastZip;
    private int dp(int x) { return Math.round(x*getResources().getDisplayMetrics().density); }
    private TextView text(String s,int size,int color) {
        TextView t=new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(color); t.setPadding(0,dp(8),0,dp(8)); return t;
    }
    private Button button(String s,LinearLayout parent) {
        Button b=new Button(this); b.setText(s); b.setAllCaps(false); b.setTextColor(Color.rgb(7,26,28));
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(95,226,201)));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(54)); p.setMargins(0,dp(5),0,dp(5)); parent.addView(b,p); return b;
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout page=new LinearLayout(this); page.setOrientation(LinearLayout.VERTICAL); page.setPadding(dp(22),dp(24),dp(22),dp(16));
        page.setBackgroundColor(Color.rgb(12,20,27));
        ScrollView scroll=new ScrollView(this); scroll.setFillViewport(true); scroll.addView(page);
        scroll.setOnApplyWindowInsetsListener((v,insets)->{
            page.setPadding(dp(22)+insets.getSystemWindowInsetLeft(),dp(12)+insets.getSystemWindowInsetTop(),
                    dp(22)+insets.getSystemWindowInsetRight(),dp(16)+insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(scroll);
        page.addView(text("本机读取 / 离线构建",13,0xff65dec9));
        TextView title=text("杜比模块生成器",29,Color.WHITE); title.setTypeface(null,Typeface.BOLD); page.addView(title);
        page.addView(text("科比 · LunarisDolby 来源\n预览版 0.1.0 · 建议 KSU + MOUNTIFY",14,0xff9db2c0));
        status=text("等待操作",17,0xff65dec9); page.addView(status);
        page.addView(text("只读当前系统，生成 ZIP 后由你保存和刷入。\n不自动安装、不重启、不常驻。请保持前台等待完成。\n读取可能包含其他模块挂载，建议在未启用杜比的系统生成。",14,0xffc4cfd7));
        root=button("① 检查环境并授权 ROOT",page);
        generate=button("② 读取系统并生成模块",page);
        save=button("③ 保存模块 ZIP",page); save.setEnabled(false);
        cancel=button("取消当前任务",page); cancel.setVisibility(View.GONE);
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal); progress.setIndeterminate(true); progress.setVisibility(View.GONE); page.addView(progress);
        logs=text("尚无构建记录",12,0xffa8bac7); logs.setTypeface(Typeface.MONOSPACE); logs.setTextIsSelectable(true);
        GradientDrawable bg=new GradientDrawable(); bg.setColor(0xff14242e); bg.setCornerRadius(dp(12)); logs.setBackground(bg); logs.setPadding(dp(12),dp(12),dp(12),dp(12)); page.addView(logs);
        String stored=getPreferences(0).getString("lastZip",null);
        if (stored!=null && new File(stored).isFile()) { lastZip=new File(stored);save.setEnabled(true); }
        root.setOnClickListener(v->start(false));
        generate.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("读取当前系统")
            .setMessage("将申请 root，只读取系统文件，并在 App 私有目录生成 ZIP。不会写运行分区或安装模块。取消安装限制不代表跨 ROM 通用。继续吗？")
            .setPositiveButton("开始生成",(d,w)->start(true)).setNegativeButton("取消",null).show());
        cancel.setOnClickListener(v->{ if (bridge!=null) bridge.cancel(); log("请求取消，将在安全边界结束。"); });
        save.setOnClickListener(v->{Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_TITLE,"杜比全景+解码器_KSU.zip"); startActivityForResult(intent,SAVE);});
    }
    private void log(String value) { handler.post(()->{ if (isDestroyed())return; String s=logs.getText()+"\n"+value; logs.setText(s.substring(Math.max(0,s.length()-45000))); }); }
    private void setBusy(boolean value) {
        busy=value;root.setEnabled(!value);generate.setEnabled(!value);save.setEnabled(!value && lastZip!=null && lastZip.isFile());
        cancel.setVisibility(value?View.VISIBLE:View.GONE);progress.setVisibility(value?View.VISIBLE:View.GONE);
        if(value)getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
    private void start(boolean build) {
        if(busy)return;setBusy(true);status.setText(build?"读取与构建中…":"等待 ROOT 授权…");logs.setText("");
        bridge=new RootBridge(getApplicationContext(),this::log);
        worker.execute(()->{
            try {
                File runtime=new File(getFilesDir(),"runtime");
                copyAssets("dolby_assets",new File(runtime,"assets"));
                if(!Python.isStarted())Python.start(new AndroidPlatform(getApplicationContext()));
                log(Python.getInstance().getModule("mobile_bridge").callAttr("check_environment",runtime.getPath()).toString());
                if(!bridge.exec("id -u\n",45).trim().equals("0"))throw new IOException("未获得 root 权限");
                log("ROOT 授权通过；设备："+bridge.model());
                if(build) {
                    String result=Python.getInstance().getModule("mobile_bridge").callAttr("generate",runtime.getPath(),new File(getFilesDir(),"history").getPath(),bridge).toString();
                    lastZip=new File(new JSONObject(result).getString("zip"));
                    getPreferences(0).edit().putString("lastZip",lastZip.getPath()).apply();
                }
                handler.post(()->status.setText(build?"生成完成 · 尚未安装":"ROOT 可用"));
            } catch(Exception e) { log(e.toString()); handler.post(()->status.setText("任务未完成 · 查看日志")); }
            finally { handler.post(()->{if(!isDestroyed())setBusy(false);}); }
        });
    }
    private void copyAssets(String source,File target) throws IOException {
        String[] children=getAssets().list(source);
        if(children!=null && children.length>0) {
            if(!target.isDirectory() && !target.mkdirs())throw new IOException("无法创建资产目录");
            for(String child:children)copyAssets(source+"/"+child,new File(target,child));
        } else {
            try(InputStream in=getAssets().open(source);OutputStream out=new FileOutputStream(target)) { copy(in,out); }
        }
    }
    private static void copy(InputStream in,OutputStream out) throws IOException {
        byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request!=SAVE || result!=RESULT_OK || data==null || data.getData()==null || lastZip==null)return;
        Uri uri=data.getData();File zip=lastZip;setBusy(true);cancel.setVisibility(View.GONE);status.setText("保存中…");
        worker.execute(()->{
            try(InputStream in=new FileInputStream(zip);OutputStream out=getContentResolver().openOutputStream(uri,"wt")) {
                if(out==null)throw new IOException("无法打开保存位置");copy(in,out);handler.post(()->status.setText("已保存 · 请自行交给 KSU 安装"));
            } catch(Exception e) {log("保存失败："+e);handler.post(()->status.setText("保存失败，可重新选择位置"));}
            finally {handler.post(()->{if(!isDestroyed())setBusy(false);});}
        });
    }
    @Override public void onBackPressed() {
        if(busy){ new AlertDialog.Builder(this).setMessage("正在执行一次性任务。请先取消或等待完成，后台可能被系统回收。")
            .setPositiveButton("继续等待",null).show(); } else super.onBackPressed();
    }
    @Override protected void onDestroy() { if(bridge!=null)bridge.cancel();worker.shutdownNow();super.onDestroy(); }
}

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
    private static final String COMPAT_WARNING="警告：应要求不按 SDK、机型或设备指纹限制生成，不保证兼容。刷入可能导致无声、应用崩溃或无法开机，后果自负。请先备份并准备禁用模块的恢复方式。";
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView status,logs;
    private Button generate,root,save,cancel,patchRom,romStatus,restoreRom,romModule,cleanCache,deleteBackups;
    private EditText romPath;
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
        page.addView(text("本机读取 / 模块生成 / ROM 内置",13,0xff65dec9));
        TextView title=text("杜比模块生成器",29,Color.WHITE); title.setTypeface(null,Typeface.BOLD); page.addView(title);
        page.addView(text("科比 · LunarisDolby 来源\n预览版 0.2.4 · 原版元模块＋缺失项补挂",14,0xff9db2c0));
        status=text("等待操作",17,0xff65dec9); page.addView(status);
        page.addView(text("只读当前系统，生成 ZIP 后由你保存和刷入。\n不自动安装、不重启、不常驻。请保持前台等待完成。\n读取可能包含其他模块挂载，建议在未启用杜比的系统生成。",14,0xffc4cfd7));
        page.addView(text("本版生成模块需要元模块，建议 KSU＋MOUNTIFY。普通文件由元模块挂载，本模块只补缺失或不符项；没有有效元模块挂载时不整包接管。\n需支持早期 initrc 注入的 KSU，且开机早期能读取 /metadata；watchdog 目录不是必需项。\n切换元模块后：卸载杜比模块 → 重启 → 重新安装。保留防卡开机措施，本版尚未通过目标机开机验证。ROM 内置逻辑未改。",14,0xffffc078));
        page.addView(text(COMPAT_WARNING,14,0xffffc078));
        root=button("① 检查环境并授权 ROOT",page);
        generate=button("② 读取系统并生成模块",page);
        save=button("③ 保存模块 ZIP",page); save.setEnabled(false);
        page.addView(text("修改手机内解包 ROM",21,Color.WHITE));
        page.addView(text("与电脑端原位修改流程相同：先缓存、编译目标策略、备份，再写回此目录。只支持带 config 的完整解包 ROM，不是正在运行的系统分区。请先备份，修改成功不等于刷入必定正常。",14,0xffc4cfd7));
        romPath=new EditText(this);romPath.setSingleLine(true);romPath.setTextColor(Color.WHITE);
        romPath.setHintTextColor(0xff9db2c0);romPath.setHint("例如 /data/DNA/DNA_01");
        romPath.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        romPath.setText(getPreferences(0).getString("romPath",""));page.addView(romPath);
        romModule=button("从此 ROM 生成模块（只读）",page);
        patchRom=button("一键修改此 ROM（先备份）",page);
        romStatus=button("查询 / 恢复上次事务状态",page);
        restoreRom=button("回退此 ROM 的上次修改",page);
        cleanCache=button("清理无用缓存（保留 ZIP / 备份）",page);
        deleteBackups=button("删除此 ROM 的备份与记录",page);
        cancel=button("取消当前任务",page); cancel.setVisibility(View.GONE);
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal); progress.setIndeterminate(true); progress.setVisibility(View.GONE); page.addView(progress);
        logs=text("尚无构建记录",12,0xffa8bac7); logs.setTypeface(Typeface.MONOSPACE); logs.setTextIsSelectable(true);
        GradientDrawable bg=new GradientDrawable(); bg.setColor(0xff14242e); bg.setCornerRadius(dp(12)); logs.setBackground(bg); logs.setPadding(dp(12),dp(12),dp(12),dp(12)); page.addView(logs);
        String stored=getPreferences(0).getString("lastZip",null);
        if (stored!=null && new File(stored).isFile()) { lastZip=new File(stored);save.setEnabled(true); }
        root.setOnClickListener(v->start(false));
        generate.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("生成风险警告")
            .setMessage(COMPAT_WARNING+"\n\n将申请 root，只读取系统文件，并在 App 私有目录生成 ZIP。不会写运行分区或安装模块。文件读取、配置结构与打包错误仍会报告。继续吗？")
            .setPositiveButton("知悉风险，继续生成",(d,w)->start(true)).setNegativeButton("取消",null).show());
        patchRom.setOnClickListener(v->confirmRom(false));
        romModule.setOnClickListener(v->{
            if(romPath.getText().toString().trim().isEmpty()){romPath.setError("请输入 ROM 解包目录");return;}
            new AlertDialog.Builder(this).setTitle("从解包 ROM 生成模块")
                .setMessage("只读目录：\n"+romPath.getText().toString().trim()+"\n\n不会修改此 ROM；生成后请用保存模块 ZIP 按钮导出。不自动刷入或重启。\n\n"+COMPAT_WARNING)
                .setPositiveButton("只读生成",(d,w)->startTask("rom-module")).setNegativeButton("取消",null).show();
        });
        restoreRom.setOnClickListener(v->confirmRom(true));
        romStatus.setOnClickListener(v->startTask("status"));
        cleanCache.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("清理无用缓存")
            .setMessage("删除本工具的读取快照和已生成模块的中间文件。保留生成 ZIP、ROM 原文件备份和回退记录，不改 ROM。存在未解决的写回事务时停止清理。")
            .setPositiveButton("清理缓存",(d,w)->startTask("cache")).setNegativeButton("取消",null).show());
        deleteBackups.setOnClickListener(v->{
            if(romPath.getText().toString().trim().isEmpty()){romPath.setError("请输入 ROM 解包目录");return;}
            new AlertDialog.Builder(this).setTitle("删除备份后无法回退")
                .setMessage("目标 ROM：\n"+romPath.getText().toString().trim()+"\n\n仅删除本应用对此目录创建的已结束事务备份与构建记录，不删除 ROM 或其他工具的备份。\n\n删除不可恢复，将失去这些记录的回退能力。请先确认 ROM 已打包并另有可靠备份。")
                .setPositiveButton("确认永久删除备份",(d,w)->startTask("backups")).setNegativeButton("保留备份",null).show();
        });
        cancel.setOnClickListener(v->{ if (bridge!=null) bridge.cancel(); log("请求取消，将在安全边界结束。"); });
        save.setOnClickListener(v->{Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_TITLE,"杜比全景+解码器_KSU.zip"); startActivityForResult(intent,SAVE);});
    }
    private void log(String value) { handler.post(()->{ if (isDestroyed())return; String s=logs.getText()+"\n"+value; logs.setText(s.substring(Math.max(0,s.length()-45000))); }); }
    private void setBusy(boolean value) {
        busy=value;root.setEnabled(!value);generate.setEnabled(!value);save.setEnabled(!value && lastZip!=null && lastZip.isFile());
        patchRom.setEnabled(!value);romStatus.setEnabled(!value);restoreRom.setEnabled(!value);romModule.setEnabled(!value);romPath.setEnabled(!value);
        cleanCache.setEnabled(!value);deleteBackups.setEnabled(!value);
        cancel.setVisibility(value?View.VISIBLE:View.GONE);progress.setVisibility(value?View.VISIBLE:View.GONE);
        if(value)getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
    private void start(boolean build) {
        startTask(build?"generate":"check");
    }
    private void confirmRom(boolean restore) {
        final String target=romPath.getText().toString().trim();
        if(target.isEmpty()){romPath.setError("请输入 ROM 解包目录");return;}
        new AlertDialog.Builder(this).setTitle(restore?"确认回退 ROM":"确认原位修改 ROM")
            .setMessage("目标目录：\n"+target+"\n\n"+(restore?
                "使用本应用最近一次记录和备份回退；若文件被其他工具修改，会停止并提示，不强行覆盖。":
                "将修改此目录中的文件及 config 打包标签，先在 App 内构建并编译 SELinux，再用一次性事务备份/写回。不能保证刷入后兼容，请保留原 ROM。")+
                "\n\n不刷分区、不重启。写入阶段请保持前台；中断后先查询状态，不要重复操作。请勿在确认打包前卸载本应用，或删除 ROM 同级 .dolby-patcher-backups。")
            .setPositiveButton(restore?"回退修改":"备份并修改",(d,w)->startTask(restore?"restore":"patch"))
            .setNegativeButton("取消",null).show();
    }
    private void startTask(String operation) {
        if(busy)return;
        final String target=romPath.getText().toString().trim();
        final boolean romOperation=operation.equals("patch")||operation.equals("restore")||operation.equals("status");
        final boolean romInput=romOperation||operation.equals("rom-module")||operation.equals("backups");
        final boolean moduleBuild=operation.equals("generate")||operation.equals("rom-module");
        if(romInput && target.isEmpty()){romPath.setError("请输入 ROM 解包目录");return;}
        if(romInput)getPreferences(0).edit().putString("romPath",target).apply();
        setBusy(true);status.setText("任务进行中 · 请保持前台…");logs.setText("");
        bridge=new RootBridge(getApplicationContext(),this::log);
        worker.execute(()->{
            try {
                File runtime=new File(getFilesDir(),"runtime");
                copyAssets("dolby_assets",new File(runtime,"assets"));
                if(!Python.isStarted())Python.start(new AndroidPlatform(getApplicationContext()));
                log(Python.getInstance().getModule("mobile_bridge").callAttr("check_environment",runtime.getPath()).toString());
                if(!bridge.exec("id -u\n",45).trim().equals("0"))throw new IOException("未获得 root 权限");
                log("ROOT 授权通过；设备："+bridge.model());
                if(moduleBuild) {
                    String result=Python.getInstance().getModule("mobile_bridge").callAttr("generate",runtime.getPath(),
                        new File(getFilesDir(),"history").getPath(),bridge,operation.equals("rom-module")?target:null).toString();
                    lastZip=new File(new JSONObject(result).getString("zip"));
                    getPreferences(0).edit().putString("lastZip",lastZip.getPath()).apply();
                }
                if(romOperation) {
                    Python.getInstance().getModule("mobile_bridge").callAttr("rom_operation",runtime.getPath(),
                        new File(getFilesDir(),"history").getPath(),bridge,target,operation);
                }
                if(operation.equals("cache")||operation.equals("backups")) {
                    Python.getInstance().getModule("mobile_bridge").callAttr("cleanup",runtime.getPath(),
                        new File(getFilesDir(),"history").getPath(),bridge,target,operation);
                }
                final String done=moduleBuild?"生成完成 · 尚未安装":operation.equals("patch")?
                    "ROM 修改完成 · 未刷机":operation.equals("restore")?"ROM 回退完成":operation.equals("status")?"状态查询完成 · 查看日志":
                    operation.equals("cache")||operation.equals("backups")?"清理完成 · 查看日志":"ROOT 可用";
                handler.post(()->status.setText(done));
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

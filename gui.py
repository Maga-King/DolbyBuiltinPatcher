"""In-place local/ADB frontend; backups and history are automatic."""
import os
import json
import queue
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, StringVar
import customtkinter as c
from core import VERSION, inspect_rom, apply_session, read
from patcher_workflow import patch_local
from adb_mode import devices, run_adb, apply_remote, monitor_remote
from ksu_module import generate_module


class App(c.CTk):
    def __init__(self):
        c.set_appearance_mode('light');c.set_default_color_theme('blue')
        super().__init__()
        self.title('杜比原生内置助手 · '+VERSION)
        self.geometry('990x780');self.minsize(880,680);self.configure(fg_color='#F3F5F8')
        self.events=queue.Queue();self.busy=False;self.session=None;self.controls=[];self.device_map={}
        self.mode=StringVar(value='电脑 ROM');self.rom=StringVar();self.remote=StringVar()
        self.device=StringVar(value='请刷新并选择设备')
        self.status=StringVar(value='选择解包目录后直接修改；备份和记录自动保留，无需设置输出目录。')
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(4,weight=1)
        header=c.CTkFrame(self,fg_color='transparent');header.grid(row=0,column=0,sticky='ew',padx=28,pady=(24,16))
        c.CTkLabel(header,text='杜比原生内置助手',font=('Microsoft YaHei UI',27,'bold'),text_color='#17202C').pack(anchor='w')
        c.CTkLabel(header,text='ColorOS 17  ·  ROM 内置补丁 / KSU 模块生成  ·  自动备份',font=('Microsoft YaHei UI',13),text_color='#647084').pack(anchor='w',pady=(5,0))
        form=c.CTkFrame(self,fg_color='white',corner_radius=14);form.grid(row=1,column=0,sticky='ew',padx=28)
        form.grid_columnconfigure(1,weight=1)
        switch=c.CTkSegmentedButton(form,values=['电脑 ROM','ADB 手机 ROM','ADB 实时读取'],variable=self.mode,command=self.change_mode)
        switch.grid(row=0,column=0,columnspan=3,padx=18,pady=15,sticky='w');self.controls.append(switch)
        self.pathlabel=c.CTkLabel(form,text='ROM 目录',font=('Microsoft YaHei UI',14));self.pathlabel.grid(row=1,column=0,padx=18,pady=10)
        self.entry=c.CTkEntry(form,textvariable=self.rom,height=38,font=('Microsoft YaHei UI',12));self.entry.grid(row=1,column=1,sticky='ew',pady=10);self.controls.append(self.entry)
        self.browse_button=c.CTkButton(form,text='浏览',width=90,height=38,command=self.browse);self.browse_button.grid(row=1,column=2,padx=18,pady=10);self.controls.append(self.browse_button)
        self.deviceframe=c.CTkFrame(form,fg_color='transparent');self.deviceframe.grid(row=2,column=0,columnspan=3,sticky='ew',padx=18,pady=(0,15));self.deviceframe.grid_columnconfigure(1,weight=1)
        c.CTkLabel(self.deviceframe,text='目标设备').grid(row=0,column=0,padx=(0,15))
        menu=c.CTkOptionMenu(self.deviceframe,variable=self.device,values=['请刷新并选择设备'],width=470,height=36)
        menu.grid(row=0,column=1,sticky='ew');self.device_menu=menu;self.controls.append(menu)
        refresh=c.CTkButton(self.deviceframe,text='刷新设备',width=90,height=36,command=self.refresh_devices);refresh.grid(row=0,column=2,padx=(15,0));self.controls.append(refresh)
        self.deviceframe.grid_remove()
        self.hint=c.CTkLabel(self,text='ADB 需 root。多设备手动选择；实时读取只支持生成 KSU 模块，不修改运行分区。',font=('Microsoft YaHei UI',12),text_color='#647084',anchor='w',wraplength=900)
        self.hint.grid(row=2,column=0,sticky='ew',padx=32,pady=(10,12))
        bar=c.CTkFrame(self,fg_color='transparent');bar.grid(row=3,column=0,sticky='ew',padx=28,pady=(0,14))
        self.action_buttons={}
        for label,fn,primary in [('检查 ROM',self.inspect,False),('一键修改 ROM',self.build,True),('生成 KSU 模块',self.module,True),('回退修改',self.restore,False),('恢复任务状态',self.resume,False)]:
            button=c.CTkButton(bar,text=label,command=fn,width=140,height=40,font=('Microsoft YaHei UI',13),fg_color='#0067C0' if primary else '#DFE8F3',text_color='white' if primary else '#17314C',hover_color='#005AAB' if primary else '#CFDDF0')
            button.pack(side='left',padx=(0,10));self.controls.append(button)
            self.action_buttons[label]=button
        self.logs=c.CTkTextbox(self,font=('Microsoft YaHei UI',12),fg_color='white',text_color='#223247',corner_radius=12)
        self.logs.grid(row=4,column=0,sticky='nsew',padx=28)
        self.logs.insert('end','一键修改：读取所选解包 ROM → 合并配置/编译策略 → 备份 → 原位写回。\nADB 模式只下载所需输入，写回改动文件。任务中断请先“恢复任务状态”，不要重复安装。\n修改的是解包文件，完成后仍需用 DNA 等工具重新打包。\n')
        self.logs.insert('end','生成 KSU 模块：选择保存 ZIP 的位置 → 只读构建；不会修改 ROM、安装或重启。需要元模块，目标机运行仍需实测。\n实时模式读取当前可见分区，可能包含其他模块挂载，不保证是纯净出厂内容。\n')
        foot=c.CTkFrame(self,fg_color='transparent');foot.grid(row=5,column=0,sticky='ew',padx=28,pady=16)
        self.progress=c.CTkProgressBar(foot,height=5);self.progress.pack(fill='x');self.progress.set(0)
        c.CTkLabel(foot,textvariable=self.status,font=('Microsoft YaHei UI',12),anchor='w',wraplength=900,justify='left').pack(fill='x',pady=(8,0))
        self.open_button=c.CTkButton(foot,text='打开记录 / 备份',width=150,command=self.open_output,state='disabled');self.open_button.pack(anchor='e',pady=(7,0))
        self.after(100,self.poll);self.protocol('WM_DELETE_WINDOW',self.close)

    def change_mode(self,_=None):
        live=self.mode.get()=='ADB 实时读取'
        remote=self.mode.get()!='电脑 ROM'
        self.entry.configure(textvariable=self.remote if remote else self.rom)
        self.pathlabel.configure(text='当前系统（只读）' if live else '手机解包路径' if remote else 'ROM 目录')
        self.entry.configure(state='disabled' if live else 'normal')
        if live:self.entry.grid_remove()
        else:self.entry.grid()
        self.browse_button.configure(state='disabled' if remote else 'normal')
        if remote:self.deviceframe.grid()
        else:self.deviceframe.grid_remove()
        for name in ('一键修改 ROM','回退修改','恢复任务状态'):
            self.action_buttons[name].configure(state='disabled' if live else 'normal')
        self.hint.configure(text='实时只读 /system、/system_ext、/product、/vendor、/odm；可能包含其他模块挂载。仅生成 KSU ZIP。' if live else 'ADB 需 root。多设备手动选择；手机解包路径示例：/data/DNA/DNA_AB。不会刷分区或重启。')

    def browse(self):
        value=filedialog.askdirectory(parent=self)
        if value:self.rom.set(value)

    def log(self,message):self.events.put(('log',message))

    def start(self,fn):
        if self.busy:return
        self.busy=True
        for control in self.controls:control.configure(state='disabled')
        self.open_button.configure(state='disabled');self.progress.configure(mode='indeterminate');self.progress.start()
        def work():
            try:self.events.put(('done',fn()))
            except Exception as e:self.events.put(('error',(str(e),traceback.format_exc())))
        threading.Thread(target=work,daemon=True).start()

    def refresh_devices(self):
        def work():self.events.put(('devices',devices()))
        self.start(work)

    def target(self):
        if self.mode.get()!='电脑 ROM':
            serial=self.device_map.get(self.device.get())
            if not serial:
                messagebox.showerror('请选择设备','请刷新列表，然后手动选择一个已授权设备。',parent=self);return None
            if self.mode.get()=='ADB 实时读取':return serial,None
            if not self.remote.get().strip():
                messagebox.showerror('请输入目录','请输入手机内 ROM 解包目录，例如 /data/DNA/DNA_AB。',parent=self);return None
            return serial,self.remote.get().strip()
        if not self.rom.get().strip():
            messagebox.showerror('请选择目录','请选择电脑内 ROM 解包目录。',parent=self);return None
        return None,self.rom.get().strip()

    def inspect(self):
        target=self.target()
        if not target:return
        serial,path=target
        def work():
            if path is None:
                from ksu_module import inspect_live
                return str(inspect_live(serial,self.log))
            if serial:return str(run_adb(serial,path,self.log,inspect_only=True))
            _,info=inspect_rom(path);self.log('检查通过：'+info['model']+' / SDK '+info['sdk'])
            self.log('完整策略编译会在修改前执行。')
        self.start(work)

    def build(self):
        if self.mode.get()=='ADB 实时读取':
            messagebox.showerror('只读模式','实时模式只支持生成 KSU 模块，不允许写回。',parent=self);return
        target=self.target()
        if not target:return
        serial,path=target
        if not messagebox.askyesno('确认原位修改',f'将备份并直接修改以下解包 ROM：\n{path}\n'+(f'设备：{serial}\n' if serial else '')+'不会刷入系统分区或重启。是否继续？',parent=self):return
        def work():return str(run_adb(serial,path,self.log) if serial else patch_local(path,self.log))
        self.start(work)

    def module(self):
        target=self.target()
        if not target:return
        serial,path=target;live=self.mode.get()=='ADB 实时读取'
        destination=filedialog.asksaveasfilename(parent=self,title='保存 KSU 模块（不会安装）',
                    defaultextension='.zip',initialfile='LunarisDolby_C17_KSU_'+VERSION+'.zip',
                    filetypes=[('KSU 模块 ZIP','*.zip')],confirmoverwrite=True)
        if not destination:return
        if not messagebox.askyesno('确认只读生成',
                f'来源：{"当前系统分区（可能含其他模块挂载）" if live else path}\n设备：{serial or "电脑目录"}\n保存：{destination}\n\n仅生成，需要 KSU 元模块；尚不保证所有元模块运行兼容。不会安装、写回或重启。',parent=self):return
        self.start(lambda:str(generate_module(destination,root=path,serial=serial,live=live,log=self.log)))

    def choose_session(self):
        return filedialog.askdirectory(title='选择含 report.json / adb-session.json 的自动备份构建目录',parent=self)

    def restore(self):
        if self.mode.get()=='ADB 实时读取':return
        session=self.choose_session()
        if not session:return
        connection=Path(session)/'adb-session.json'
        if connection.is_file():
            record=json.loads(read(connection))
            if not messagebox.askyesno('确认回退设备',f'将回退记录绑定的设备：\n{record["serial"]}\n目录：{record["root"]}\n不会使用其他连接设备。是否继续？',parent=self):return
        def work():
            if (Path(session)/'adb-session.json').is_file():apply_remote(session,restore=True,log=self.log)
            else:apply_session(session,restore=True,log=self.log)
            return session
        self.start(work)

    def resume(self):
        if self.mode.get()=='ADB 实时读取':return
        session=self.choose_session()
        if not session:return
        self.start(lambda:str(monitor_remote(session,log=self.log)))

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='log':self.logs.insert('end',value+'\n');self.logs.see('end');self.status.set(value)
                elif kind=='devices':
                    connected=[d for d in value if d['state']=='device']
                    self.device_map={d['serial']+' | '+d['model']:d['serial'] for d in connected}
                    options=list(self.device_map)
                    self.device_menu.configure(values=options or ['没有已授权设备'])
                    self.device.set(options[0] if len(options)==1 else '请手动选择设备' if options else '没有已授权设备')
                    for d in value:self.logs.insert('end',f'{d["serial"]}  {d["model"]}  {d["state"]}\n')
                else:
                    self.busy=False;self.progress.stop();self.progress.configure(mode='determinate');self.progress.set(1 if kind=='done' else 0)
                    for control in self.controls:control.configure(state='normal')
                    self.change_mode()
                    if kind=='done':
                        if value:self.session=value
                        self.status.set('完成；记录/备份已保留。' if value else '检查/刷新完成。')
                    else:
                        self.logs.insert('end',value[1]+'\n');self.logs.see('end');self.status.set('未完成：'+value[0])
                        messagebox.showerror('任务未完成',value[0],parent=self)
                    self.open_button.configure(state='normal' if self.session else 'disabled')
        except queue.Empty:pass
        self.after(100,self.poll)

    def open_output(self):
        if self.session:os.startfile(self.session)

    def close(self):
        if self.busy:messagebox.showinfo('正在处理','请等待事务完成。ADB 中断时保留记录，重连后恢复任务状态。',parent=self);return
        self.destroy()

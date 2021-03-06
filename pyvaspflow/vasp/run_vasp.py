#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-


from pyvaspflow.vasp import prep_vasp
from pyvaspflow.utils import read_json,add_log_shell_file
from time import sleep,ctime
import os,subprocess,shutil,logging


def is_inqueue(job_id):
    p = subprocess.Popen('squeue',stdout=subprocess.PIPE)
    que_res = p.stdout.readlines()
    p.stdout.close()
    for ii in que_res:
        if str(job_id) in ii.decode('utf-8'):
            return True
    return False

def submit_job(job_name):
    res = subprocess.Popen(['sbatch', './job.sh'],stdout=subprocess.PIPE,cwd=job_name)
    std = res.stdout.readlines()
    res.stdout.close()
    pid = std[0].decode('utf-8').split()[-1]
    logging.info(job_name+" calculation has been submitted, the queue id is "+pid)
    logging.info("The work dir is "+os.path.join(os.getcwd(),job_name))
    return pid

def submit_job_without_job(job_name,node_name,cpu_num,node_num=1,submit_job_idx=0):
    has_write_job = False
    for idx in range(len(node_name)):
        if node_is_idle(node_name[idx]):
            write_job_file(job_name,node_name[idx],cpu_num[idx],node_num)
            has_write_job = True
            node_submitted = node_name[idx]
            break
    if not has_write_job:
        write_job_file(job_name,node_name[submit_job_idx],cpu_num[submit_job_idx],node_num)
        node_submitted = node_name[submit_job_idx]
        submit_job_idx += 1
        if submit_job_idx == len(node_name):
            submit_job_idx = 0
    res = subprocess.Popen(['sbatch', './job.sh'],stdout=subprocess.PIPE,cwd=job_name)
    std = res.stdout.readlines()
    res.stdout.close()
    pid = std[0].decode('utf-8').split()[-1]
    logging.info(job_name+" calculation has been submitted, the queue id is "+pid)
    logging.info("The work dir is "+os.path.join(os.getcwd(),job_name))
    sleep(5)
    return pid,submit_job_idx

def node_is_idle(node_name):
    p = subprocess.Popen('sinfo',stdout=subprocess.PIPE)
    sinf_res = p.stdout.read()
    sinf_res = sinf_res.decode('utf-8').split('\n')
    p.stdout.close()
    for line in sinf_res:
        if 'idle' in line and node_name in line:
            return True
    return False

def is_job_running(pid):
    p = subprocess.Popen('squeue',stdout=subprocess.PIPE)
    sinf_res = p.stdout.read()
    sinf_res = sinf_res.decode('utf-8').split('\n')
    p.stdout.close()
    for line in sinf_res:
        if ' R ' in  line and pid in line:
            return True
    return False

def is_job_pd(pid):
    p = subprocess.Popen('squeue',stdout=subprocess.PIPE)
    sinf_res = p.stdout.read()
    sinf_res = sinf_res.decode('utf-8').split('\n')
    p.stdout.close()
    for line in sinf_res:
        if ' PD ' in  line and pid in line:
            return True
    return False

def has_job_finished(folder):
    if (not os.path.isfile(os.path.join(folder,"EIGENVAL"))) or (not os.path.isfile(os.path.join(folder,"EIGENVAL"))):
        return False
    size = os.path.getsize(os.path.join(folder,"EIGENVAL"))+os.path.getsize(os.path.join(folder,"DOSCAR"))
    if size < 1000:
        return False
    return True


def get_number_of_running_shell_files(shell_file,main_pid):
    p = subprocess.Popen(['ps', '-ef'],stdout=subprocess.PIPE)
    que_res = p.stdout.readlines()
    p.stdout.close()
    pid_res = [i  for i in que_res if 'bash '+shell_file in i.decode("utf-8") and str(main_pid) in i.decode("utf-8") ]
    p.kill()
    return len(pid_res)

def write_job_file(job_name,node_name,cpu_num,node_num):
    json_f = read_json()
    with open(job_name+'/job.sh','w') as f:
        f.writelines('#!/bin/bash \n')
        f.writelines('#SBATCH -J '+job_name+'\n')
        f.writelines('#SBATCH -p '+node_name+' -N '+ str(int(node_num)) +' -n '+str(int(cpu_num))+'\n\n')
        f.writelines(json_f['job']['prepend']+'\n')
        f.writelines(json_f['job']['exec']+'\n')

# def job_status(job_id):
#     res = run('squeue','grep '+str(job_id)).std_out_err
#     stdout = res[0].split()
#     if stdout == [] :
#         print('Not found job_id in queue')
#         return  None
#     return dict(zip(['job_id','part','name','user','status','time','node','nodelist'],stdout))

def clean_parse(kw,key,def_val):
    val = kw.get(key,def_val)
    kw.pop(key,None)
    return val,kw

def _submit_job(job_name,cpu_num):
    js = read_json()
    prep = js['job']['prepend']
    exe = js['job']['exec']
    subprocess.check_output(prep+' && '+'mpirun -n '+str(cpu_num)+' '+exe.split()[-1],shell=True,cwd=job_name)

def run_single_vasp(job_name,is_login_node=False,cpu_num=24,cwd="",main_pid=None):
    if not main_pid:
        main_pid = os.getpid()
    job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(main_pid))
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
        datefmt='%a, %d %b %Y %H:%M:%S',
        filename=os.path.join(cwd,'run-'+str(main_pid)+'.log'),
        filemode='a')
    if is_login_node:
        logging.warning(job_name+" calculation Runing at logging node")
        _submit_job(job_name,cpu_num=cpu_num)
        logging.info(job_name+" in dir of "+cwd+" calculation finished")
    else:
        logging.info(job_name+" calculation has submitted at calculation node")
        job_id = submit_job(job_name)
        # pid = os.getpid()
        # job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(pid))
        with open(job_id_file,'a') as f:
            f.writelines(job_id+"\n")
        while True:
            if not is_inqueue(job_id):
                logging.info(job_name+" in dir of "+os.getcwd()+" calculation finished")
                break
            sleep(5)
    # if not has_job_finished(os.path.join(os.getcwd(),job_name)):
    #     logging.info(job_name+" in dir of "+cwd+" calculation does not finish, another calculation will be submitted")
    #     if os.path.getsize(os.path.join(os.getcwd(),job_name,'CONTCAR')) < 1:
    #         logging.info(job_name+" in dir of "+cwd+" calculation does not finish, another calculation can not be submitted for one ion step does not finished")
    #         return
    #     poscar_size = os.path.getsize(os.path.join(os.getcwd(),job_name,'POSCAR'))
    #     if os.path.isfile(os.path.join(os.getcwd(),job_name,'CONTCAR')) and os.path.getsize(os.path.join(os.getcwd(),job_name,'CONTCAR'))>=poscar_size:
    #         shutil.copyfile(os.path.join(os.getcwd(),job_name,'CONTCAR'),os.path.join(os.getcwd(),job_name,'POSCAR'))
    #     run_single_vasp(job_name,is_login_node,cpu_num,cwd,main_pid)
    #     # os.remove(job_id_file)

def run_single_vasp_without_job(job_name,node_name,cpu_num,node_num=1,cwd="",main_pid=None):
    if not main_pid:
        main_pid = os.getpid()
        job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(main_pid))
    else:
        job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(main_pid))
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
        datefmt='%a, %d %b %Y %H:%M:%S',
        filename=os.path.join(cwd,'run-'+str(main_pid)+'.log'),
        filemode='a')
    job_id,submit_job_idx = submit_job_without_job(job_name,node_name,cpu_num,node_num=1)
    with open(job_id_file,'a') as f:
        f.writelines(job_id+"\n")
    sleep(5)
    while True:
        for idx,nname in enumerate(node_name):
            if node_is_idle(nname) and is_job_pd(job_id):
                os.system("scancel "+job_id)
                logging.info(job_name+" has been scancelled, the queue id is "+job_id)
                write_job_file(job_name,nname,cpu_num[idx],node_num)
                res = subprocess.Popen(['sbatch', './job.sh'],stdout=subprocess.PIPE,cwd=job_name)
                std = res.stdout.readlines()
                res.stdout.close()
                job_id = std[0].decode('utf-8').split()[-1]
                logging.info(job_name+" has been submitted at "+nname+" node, the queue id is "+job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(job_id+"\n")
            sleep(5)
        if not is_inqueue(job_id):
            logging.info(job_name+" in dir of "+os.getcwd()+" calculation finished")
            break
        sleep(5)
    # if not has_job_finished(os.path.join(os.getcwd(),job_name)):
    #     logging.info(job_name+" in dir of "+os.getcwd()+" calculation does not finish, another calculation will be submitted")
    #     if os.path.getsize(os.path.join(os.getcwd(),job_name,'CONTCAR')) < 1:
    #         logging.info(job_name+" in dir of "+os.getcwd()+" calculation does not finish, another calculation can not be submitted for one ion step does not finished")
    #         return
    #     poscar_size = os.path.getsize(os.path.join(os.getcwd(),job_name,'POSCAR'))
    #     if os.path.isfile(os.path.join(os.getcwd(),job_name,'CONTCAR')) and os.path.getsize(os.path.join(os.getcwd(),job_name,'CONTCAR'))>=poscar_size:
    #         shutil.copyfile(os.path.join(os.getcwd(),job_name,'CONTCAR'),os.path.join(os.getcwd(),job_name,'POSCAR'))
    #     run_single_vasp_without_job(job_name,node_name,cpu_num,node_num,cwd,main_pid)

def run_multi_vasp(job_name='task',end_job_num=1,start_job_num=0,job_list=None,par_job_num=4,cwd=""):
    pid = os.getpid()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename=os.path.join(cwd,'run-'+str(pid)+'.log'),
                        filemode='a')
    job_inqueue_num = lambda id_pool:[is_inqueue(i) for i in id_pool].count(True)
    job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(pid))

    if job_list is not None:
        start_job_num,end_job_num,par_job_num = 0,len(job_list)-1,int(par_job_num)
        jobid_pool = []
        idx = 0
        for ii in range(min(par_job_num,end_job_num)):
            _job_id = submit_job(job_name+str(job_list[ii]))
            jobid_pool.append(_job_id)
            with open(job_id_file,'a') as f:
                f.writelines(_job_id+"\n")
            idx += 1
        if idx == end_job_num+1:
            return
        while True:
            inqueue_num = job_inqueue_num(jobid_pool)
            logging.info(str(inqueue_num)+" in queue")
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id = submit_job(job_name + str(job_list[idx]))
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
            sleep(60)
            if idx == end_job_num+1 and job_inqueue_num(jobid_pool) == 0:
                break
    else:
        start_job_num,end_job_num,par_job_num = int(start_job_num),int(end_job_num),int(par_job_num)
        jobid_pool = []
        idx = start_job_num
        for ii in range(min(par_job_num,end_job_num-start_job_num)):
            _job_id = submit_job(job_name+str(ii+start_job_num))
            jobid_pool.append(_job_id)
            with open(job_id_file,'a') as f:
                f.writelines(_job_id+"\n")
            idx += 1
        if idx == end_job_num+1:
            return
        while True:
            inqueue_num = job_inqueue_num(jobid_pool)
            logging.info(str(inqueue_num)+" in queue")
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id = submit_job(job_name + str(idx))
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
            sleep(60)
            if idx == end_job_num+1 and job_inqueue_num(jobid_pool) == 0:
                break
    # os.remove(job_id_file)


def run_multi_vasp_without_job(job_name='task',end_job_num=1,node_name="short_q",cpu_num=24,node_num=1,start_job_num=0,job_list=None,par_job_num=4,cwd=""):
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename=os.path.join(cwd,'run-'+str(os.getpid())+'.log'),
                        filemode='a')
    job_inqueue_num = lambda id_pool:[is_inqueue(i) for i in id_pool].count(True)
    main_pid = os.getpid()
    job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(main_pid))
    with open(job_id_file,'w') as f:
        pass
    submit_job_idx = 0
    if job_list is not None:
        start_job_num,end_job_num,par_job_num = 0,len(job_list)-1,int(par_job_num)
        jobid_pool = []
        idx = 0
        for ii in range(min(par_job_num,end_job_num)):
            _job_id,submit_job_idx = submit_job_without_job(job_name+str(job_list[ii]),node_name,cpu_num,node_num=1,submit_job_idx=submit_job_idx)
            jobid_pool.append(_job_id)
            with open(job_id_file,'a') as f:
                f.writelines(_job_id+"\n")
            idx += 1
        if idx == end_job_num+1:
            return
        while True:
            inqueue_num = job_inqueue_num(jobid_pool)
            logging.info(str(inqueue_num)+" in queue")
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id,submit_job_idx = submit_job_without_job(job_name + str(job_list[idx]),node_name,cpu_num,node_num=1,submit_job_idx=submit_job_idx)
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
                sleep(5)
            sleep(10)
            if idx == end_job_num+1 and job_inqueue_num(jobid_pool) == 0:
                break
    else:
        start_job_num,end_job_num,par_job_num = int(start_job_num),int(end_job_num),int(par_job_num)
        jobid_pool = []
        idx = start_job_num
        for ii in range(min(par_job_num,end_job_num-start_job_num)):
            _job_id,submit_job_idx = submit_job_without_job(job_name+str(ii+start_job_num),node_name,cpu_num,node_num=1,submit_job_idx=submit_job_idx)
            jobid_pool.append(_job_id)
            with open(job_id_file,'a') as f:
                f.writelines(_job_id+"\n")
            idx += 1
        if idx == end_job_num+1:
            return
        while True:
            inqueue_num = job_inqueue_num(jobid_pool)
            logging.info(str(inqueue_num)+" in queue")
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id,submit_job_idx = submit_job_without_job(job_name + str(idx),node_name,cpu_num,node_num=1,submit_job_idx=submit_job_idx)
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
                sleep(5)
            sleep(10)
            if idx == end_job_num+1 and job_inqueue_num(jobid_pool) == 0:
                break
    os.remove(job_id_file)


def run_multi_vasp_with_shell(work_name,shell_file,end_job_num=1,start_job_num=0,job_list=None,par_job_num=4):
    cwd = os.getcwd()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename=os.path.join(cwd,'run-'+str(os.getpid())+'.log'),
                        filemode='a')
    main_pid = os.getpid()
    job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(main_pid))

    if job_list:
        pass
    else:
        start_job_num,end_job_num,par_job_num = int(start_job_num),int(end_job_num),int(par_job_num)
        pid_pool = []
        idx = start_job_num
        for ii in range(min(par_job_num,end_job_num-start_job_num)):
            if os.path.isdir(work_name+str(idx)):
                shutil.rmtree(work_name+str(idx))
            os.makedirs(work_name+str(idx))
            shutil.copyfile("POSCAR"+str(idx),work_name+str(idx)+"/POSCAR")
            new_lines = add_log_shell_file(shell_file,cwd,main_pid)
            with open(work_name+str(idx)+"/"+shell_file,"w") as f:
                f.writelines(new_lines)
            res = subprocess.Popen(['bash',shell_file],cwd=work_name+str(idx))
            pid_pool.append(res.pid)
            idx += 1
            sleep(5)
        if idx == end_job_num+1:
            return
        while True:
            inqueue_num = get_number_of_running_shell_files(shell_file,main_pid)
            logging.info(str(inqueue_num)+" in queue")
            if inqueue_num < par_job_num and idx < end_job_num+1:
                if os.path.isdir(work_name+str(idx)):
                    shutil.rmtree(work_name+str(idx))
                os.makedirs(work_name+str(idx))
                shutil.copyfile("POSCAR"+str(idx),work_name+str(idx)+"/POSCAR")
                new_lines = add_log_shell_file(shell_file,cwd,main_pid)
                with open(work_name+str(idx)+"/"+shell_file,"w") as f:
                    f.writelines(new_lines)
                res = subprocess.Popen(['bash',shell_file],cwd=work_name+str(idx))
                pid_pool.append(res.pid)
                idx += 1
                sleep(5)
            if idx == end_job_num+1 and get_number_of_running_shell_files(shell_file,main_pid) == 0:
                break
            sleep(60)

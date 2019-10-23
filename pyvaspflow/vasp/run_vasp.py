#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-


from pyvaspflow.vasp import prep_vasp
from pyvaspflow.utils import read_json
from time import sleep
import os,subprocess,shutil


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
    return std[0].decode('utf-8').split()[-1]

def submit_job_without_job(job_name,node_name,cpu_num,node_num=1):
    has_write_job = False
    for idx in range(len(node_name)):
        if node_is_idle(node_name[idx]):
            write_job_file(job_name,node_name[idx],cpu_num[idx],node_num)
            has_write_job = True
            break
    if not has_write_job:
        write_job_file(job_name,node_name[0],cpu_num[0],node_num)
    res = subprocess.Popen(['sbatch', './job.sh'],stdout=subprocess.PIPE,cwd=job_name)
    std = res.stdout.readlines()
    res.stdout.close()
    sleep(5)
    return std[0].decode('utf-8').split()[-1]

def node_is_idle(node_name):
    p = subprocess.Popen('sinfo',stdout=subprocess.PIPE)
    sinf_res = p.stdout.read()
    sinf_res = sinf_res.decode('utf-8').split('\n')
    p.stdout.close()
    for line in sinf_res:
        if 'idle' in line and node_name in line:
            return True
    return False


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

def run_single_vasp(job_name,is_login_node=False,cpu_num=20):
    if is_login_node:
        _submit_job(job_name,cpu_num=cpu_num)
    else:
        job_id = submit_job(job_name)
        pid = os.getpid()
        job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(pid))
        with open(job_id_file,'w') as f:
            f.writelines(job_id+"\n")
        while True:
            if not is_inqueue(job_id):
                break
            sleep(5)
    os.remove(job_id_file)



def run_multi_vasp(job_name='task',end_job_num=1,start_job_num=0,job_list=None,par_job_num=4):
    job_inqueue_num = lambda id_pool:[is_inqueue(i) for i in id_pool].count(True)
    pid = os.getpid()
    job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(pid))
    with open(job_id_file,'w') as f:
        pass

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
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id = submit_job(job_name + str(job_list[idx]))
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
                sleep(5)
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
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id = submit_job(job_name + str(idx))
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
                sleep(5)
            if idx == end_job_num+1 and job_inqueue_num(jobid_pool) == 0:
                break
    os.remove(job_id_file)



def run_multi_vasp_without_job(job_name='task',end_job_num=1,node_name="short_q",cpu_num=24,node_num=1,start_job_num=0,job_list=None,par_job_num=4):
    job_inqueue_num = lambda id_pool:[is_inqueue(i) for i in id_pool].count(True)
    pid = os.getpid()
    job_id_file = os.path.join(os.path.expanduser("~"),'.config','pyvaspflow',str(pid))
    with open(job_id_file,'w') as f:
        pass

    if job_list is not None:
        start_job_num,end_job_num,par_job_num = 0,len(job_list)-1,int(par_job_num)
        jobid_pool = []
        idx = 0
        for ii in range(min(par_job_num,end_job_num)):
            _job_id = submit_job_without_job(job_name+str(job_list[ii]),node_name,cpu_num,node_num=1)
            jobid_pool.append(_job_id)
            with open(job_id_file,'a') as f:
                f.writelines(_job_id+"\n")
            idx += 1
        if idx == end_job_num+1:
            return
        while True:
            inqueue_num = job_inqueue_num(jobid_pool)
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id = submit_job_without_job(job_name + str(job_list[idx]),node_name,cpu_num,node_num=1)
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
                sleep(5)
            if idx == end_job_num+1 and job_inqueue_num(jobid_pool) == 0:
                break
    else:
        start_job_num,end_job_num,par_job_num = int(start_job_num),int(end_job_num),int(par_job_num)
        jobid_pool = []
        idx = start_job_num
        for ii in range(min(par_job_num,end_job_num-start_job_num)):
            _job_id = submit_job_without_job(job_name+str(ii+start_job_num),node_name,cpu_num,node_num=1)
            jobid_pool.append(_job_id)
            with open(job_id_file,'a') as f:
                f.writelines(_job_id+"\n")
            idx += 1
        if idx == end_job_num+1:
            return
        while True:
            inqueue_num = job_inqueue_num(jobid_pool)
            if inqueue_num < par_job_num and idx < end_job_num+1:
                _job_id = submit_job_without_job(job_name + str(idx),node_name,cpu_num,node_num=1)
                jobid_pool.append(_job_id)
                with open(job_id_file,'a') as f:
                    f.writelines(_job_id+"\n")
                idx += 1
                sleep(5)
            if idx == end_job_num+1 and job_inqueue_num(jobid_pool) == 0:
                break
    os.remove(job_id_file)

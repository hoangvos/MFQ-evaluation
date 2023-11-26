''' ------------------------ '''
''' Dependencies             '''
''' ------------------------ '''
import simpy
import statistics 
import numpy.random as random
from numpy import *
import matplotlib.pyplot as plt
from kneed import DataGenerator, KneeLocator
from pyDOE import *
import pandas as pd
''' ------------------------ '''
''' Running mode, Only one   '''
''' option should be True    '''
''' ------------------------ '''
#One time simulation for short demonstration
DEMO = False                 
SIMULATE = True
#Multiple simulations to get mean value 
MULTIPLE_SIMULATION = False
#Again, multiple simulations for experiments
EXPERIMENT = False
# Experiment running for the QUANTUM effect
EXPERIMENT_QUANTUM_On_FIRST_RESPONSE = False
''' ------------------------ '''
''' Experiment list          '''
''' 2 level only              '''
''' ------------------------ '''
lambda_exp = [0.025,  0.05]
mu_exp = [0.1, 0.2]
quantum_queue_1_exp = [0.3, 3]
quantum_queue_2_exp = [0.4, 5]
lambda_io_exp = [0.03, 0.07]
mu_io_exp = [0.4, 0.9]
io_probalities_exp = [0.1, 0.3]
''' ------------------------ '''
''' Parameters               '''
''' ------------------------ '''
MAXSIMTIME = 100000
LAMBDA = 0.2
MU = 0.1
LAMBDA_IO = 0.5
MU_IO = 0.5
IO_PROBALITIES = 0.2
QUANTUM_QUEUE_1 = 4
QUANTUM_QUEUE_2 = 8
POPULATION = 50000000
SERVICE_DISCIPLINE = 'RR'
LOGGED = False 
VERBOSE = False
NSIM = 30
NUM_CPU = 3
''' ------------------------ '''
''' DES model                '''
''' ------------------------ '''
# This is for data recording, haven't use anything yet
# may come handy later so I left it there
class Record:
    total_burst = []   # sum of burst times at each step
    total_hist_t = []  # step at which burst total was recorded
    q_size = []        # size of queue at each step
    q_time = []        # step at which queue size was recorded
    times = []
    mean_burst = []
    wait_t = []
    trnd_t = []
    mean_wait = []
    mean_trnd = []
    arrivals = []      # arrival times of jobs
    finish = []        # finish time of jobs
class Job:
    def __init__(self,server, name, arrtime, duration, remain, allotment, first_response, priority, io, lam_io, mu_io):
        self.server = server
        self.env = self.server.env
        self.io = io
        self.lam_io = lam_io
        self.mu_io = mu_io
        self.priority = priority
        self.name = name
        self.arrtime = arrtime
        self.service_t = duration
        self.remain_t = remain
        self.allotment = allotment
        self.first_response = first_response
        self.wait_t = 0
        self.trnd_t = 0
        self.resp_t = 0
        self.io_trigger = simpy.Event(self.server.env)
        self.io_service_t = 0
        self.io_arrtime = 0
        self.past_queue = 1
        self.processing_job = simpy.Event(self.env)
        self.processing = simpy.Event(self.env)
        self.processing = simpy.Event(self.env)
        self.trigger_event_source = simpy.Event(env)

    def __str__(self):
        return '%s at %d, length %d' %(self.name, self.arrtime, self.duration)

def SJF( job ):
    return job.duration

''' 
A server
- env: SimPy environment
- strat: - FIFO: First In First Out
         - RR: Round-robin
'''
class Server:
    def __init__(self, env):
        self.env = env
        """ Create resources """
        self.cpu = simpy.PreemptiveResource(env, capacity = NUM_CPU)
        """ Create resources """
        self.queue_1 = []
        self.queue_2 = []
        self.queue_3 = []
        self.io_queue = []
        self.jobServing = 0
        self.idleTime = 0

        self.serversleeping = None
        self.server_io_request = None
        
        ''' statistics '''
        self.waitingTime = 0
        self.jobsDone = 0
        self.serviceTime = 0
        self.responseTime = 0
        self.first_responsetime = 0     # accumulating the first response time
        self.turnaroundTime = 0
        self.timeStamp = 0
        self.jobsTotal = 0              # total jobs had been first responsed
        self.jobsInSysCount = []        # record number of current jobs in the system
        self.jobsInSysCount_t = []      # mark down the time when record occurs
        self.numJobsWithTimes = []      # for mean job in system calculation. don't judge the name tho :(
        
        self.job_in_sys_count = []      # try to count the number of job in sys with even length time
        self.job_in_sys_count_avg = []  # number of job in sys * time length
        self.length = []                # list to store the type of length of queue

        ''' register a new server process '''
        env.process(self.serve())
        env.process(self.timeout())
        env.process(self.handle_io_request())
    def handle_io_request(self):
        while True:
            if len(self.io_queue) == 0:
                self.server_io_request = self.env.process(self.waiting_io(self.env))
                yield self.server_io_request
            else:
                j = self.io_queue.pop(0)
                self.jobServing += 1
                if VERBOSE:
                    print('{0:.2f}: {1:s} is implementing IO.'.format(self.env.now, j.name))
                yield self.env.timeout(j.io_service_t)
                self.jobServing -= 1
                j.service_t += j.io_service_t
                if VERBOSE:
                    print('{0:.2f}: IO finished, {1:s} returns back to queue {2:d}.'.format(self.env.now, j.name, j.past_queue))
                if j.past_queue == 1:
                    self.queue_1.append(j) 
                elif j.past_queue == 2:
                    self.queue_2.append(j)
                elif j.past_queue == 3:
                    self.queue_3.append(j)
                
    def serve(self):
        while True:
            ''' 
            do nothing, just change server to idle
            and then yield a wait event which takes infinite time
            '''
            if len(self.queue_1) == 0 and len(self.queue_2) == 0 and len(self.queue_3) == 0:
                self.serversleeping = env.process( self.waiting( self.env))
                t1 = self.env.now
                yield self.serversleeping
                self.idleTime += self.env.now - t1
            else:
                ''' 
                record the number of job in system:
                number of job in waiting queue (jobs)
                '''
                if VERBOSE:
                    print('Number of jobs in the sys: {0:d}' .format(len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + len(self.io_queue) + self.jobServing))
                    print('Queued 1: ')
                    for i in range(len(self.queue_1)):
                            print(self.queue_1[i].name, end=" | ")
                    print('\n')
                    print('Queued 2: ')
                    for i in range(len(self.queue_2)):
                            print(self.queue_2[i].name, end=" | ")
                    print('\n')
                    print('Queued 3: ')
                    for i in range(len(self.queue_3)):
                            print(self.queue_3[i].name, end=" | ")
                    print('\n')
                    print('IO queue: ')
                    for i in range(len(self.io_queue)):
                            print(self.io_queue[i].name, end=" | ")
                    print('\n')
                ''' get the first job to be served'''
                if len(self.queue_1) > 0:
                    with self.cpu.request(priority = 1) as req:
                        try:
                            yield req
                            if len(self.queue_1) > 0:
                                j = self.queue_1.pop(0)
                            else:
                                continue
                        except simpy.Interrupt as interrupt:
                            continue 
                    self.env.process(self.handle_queue_1(j))
                    yield j.trigger_event_source
                elif len(self.queue_2) > 0:
                    with self.cpu.request(priority = 2) as req:
                        try:
                            yield req
                            if len(self.queue_2) > 0:
                                j = self.queue_2.pop(0)
                            else:
                                continue
                        except simpy.Interrupt as interrupt:
                            continue 
                    self.env.process(self.handle_queue_2(j))
                    yield j.trigger_event_source
                elif len(self.queue_3) > 0:
                    with self.cpu.request(priority = 3) as req:
                        try:
                            yield req
                            if len(self.queue_3) > 0:
                                j = self.queue_3.pop(0)
                            else:
                                continue
                        except simpy.Interrupt as interrupt:
                            continue 
                    self.env.process(self.handle_queue_3(j))
                    yield j.trigger_event_source
    def handle_queue_1(self, job):
        #print("Enter handle 1")
        with self.cpu.request(priority = job.priority) as req:
            try:
                yield req 
            except simpy.Interrupt as interrupt:
                return 0
            try:
                if job.io:
                    self.env.process(self.generate_io(job))   
                job.trigger_event_source.succeed()
                job.trigger_event_source = simpy.Event(env)
                current_time = self.env.now
                self.jobServing += 1

                if job.first_response:
                    self.jobsTotal += 1
                    current_t = self.env.now
                    self.first_responsetime += (current_t - job.arrtime)
                    job.first_response = 0
                    if VERBOSE:
                        print("{0:.2f} {1:s} first response time: {2:.2f}".format(env.now, job.name, env.now - job.arrtime))
                    """ if the job is stopped (quantum expired)"""
                if job.remain_t > job.allotment:
                    if VERBOSE:
                        print('Queued 1: ')
                        for i in range(len(self.queue_1)):
                            print(self.queue_1[i].name, end=" | ")
                        print('\n')
                        print('{0:.2f} serving:{1:s} | arr_t = {2:.2f} | l = {3:.2f}' \
                            .format(env.now, job.name, job.arrtime, job.remain_t))
                    timeout_event = self.env.timeout(job.allotment)
                    result = yield timeout_event | job.processing_job
                    
                    if timeout_event not in result:
                        #print(env.now)
                        #print('aaaaaaaaaaaaaaaaa')
                        job.remain_t -= (env.now - current_time)
                        job.allotment -= (env.now - current_time)
                        job.past_queue = 1
                        self.jobServing -= 1
                        return
                    job.processing.succeed()
                    job.processing = simpy.Event(self.env)
                    
                    job.remain_t = job.remain_t - job.allotment
                    job.allotment = QUANTUM_QUEUE_2 if job.remain_t >= QUANTUM_QUEUE_2 else job.remain_t
                    job.priority += 1 
                    self.jobServing -= 1 
                    self.queue_2.append(job)
                    if not self.serversleeping.triggered:
                        self.serversleeping.interrupt( 'Wake up, please.' )
                elif job.remain_t == job.allotment:
                    if VERBOSE:
                        print('Queued 1: ')
                        for i in range(len(self.queue_1)):
                            print(self.queue_1[i].name, end=" | ")
                        print('\n')
                        print('{0:.2f} serving:{1:s} | arr_t = {2:.2f} | l = {3:.2f}'.format(env.now, job.name, job.arrtime, job.remain_t))
        
                    
                    

                    timeout_event = self.env.timeout(job.remain_t)
                    result = yield timeout_event | job.processing_job
                    if timeout_event not in result:
                        #print(env.now)
                        #print('aaaaaaaaaaaaaaaaa')
                        job.remain_t -= (env.now - current_time)
                        job.allotment -= (env.now - current_time)
                        self.jobServing -= 1
                        job.past_queue = 1
                        return
                    job.processing.succeed()
                    job.processing = simpy.Event(self.env)
                    ''' for calculating mean of job in system'''
                    ''' right before the job leaves          '''
                    ''' like 2 2 2 2 2 2 1                   '''
                    ''' mark at this   ^                     '''
                    self.jobServing -= 1
                    elapse = self.env.now - self.timeStamp
                    queueLength = len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + len(self.io_queue) + self.jobServing + 1
                    self.numJobsWithTimes.append((queueLength)*(elapse))
                    self.jobsInSysCount.append(queueLength)
                    self.jobsInSysCount_t.append(env.now)
                    self.timeStamp = self.env.now
                    finishTime = env.now
                    job.wait_t = finishTime - job.arrtime - job.service_t
                    job.trnd_t = finishTime - job.arrtime
                    self.waitingTime += job.wait_t
                    self.serviceTime += job.service_t
                    self.turnaroundTime += job.trnd_t
                    self.jobsDone += 1
                    if VERBOSE:
                        print(job.name + ': Finish at {0:.2f}, trnd_t = {1:.2f}, wait_t = {2:.2f}' \
                            .format(finishTime, job.trnd_t, job.wait_t))
                        print('{0:.2f} Number of jobs in the system at the time a job finished: {1:d}'.format(env.now,queueLength - 1))
            except simpy.Interrupt as interrupt:
                #print(interrupt)
                job.processing.succeed()
                job.processing = simpy.Event(self.env)
                pass_time = env.now - current_time
                if VERBOSE:
                    print('Queued 1: ')
                    for i in range(len(self.queue_1)):
                        print(self.queue_1[i].name, end=" | ")
                    print('\n')
                    print('{0:s} is preempted at {1:.2f}. The remaining allotment is {2:.2f}'.format(job.name, env.now, job.remain_t - pass_time))
                if env.now - current_time == job.allotment: 
                    if job.remain_t > job.allotment:
                        job.remain_t = job.remain_t - job.allotment
                        job.allotment = QUANTUM_QUEUE_2 if job.remain_t >= QUANTUM_QUEUE_2 else job.remain_t
                        job.priority += 1
                        self.jobServing -= 1
                        self.queue_2.append(job)
                        if not self.serversleeping.triggered:
                            self.serversleeping.interrupt( 'Wake up, please.' )
                    elif job.remain_t == job.allotment:
                        self.jobServing -= 1
                        elapse = self.env.now - self.timeStamp
                        queueLength = len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + len(self.io_queue) + self.jobServing + 1
                        self.numJobsWithTimes.append((queueLength)*(elapse))
                        self.jobsInSysCount.append(queueLength)
                        self.jobsInSysCount_t.append(env.now)
                        self.timeStamp = self.env.now
                        finishTime = env.now
                        job.wait_t = finishTime - job.arrtime - job.service_t
                        job.trnd_t = finishTime - job.arrtime
                        self.waitingTime += job.wait_t
                        self.serviceTime += job.service_t
                        self.turnaroundTime += job.trnd_t
                        self.jobsDone += 1
                        if VERBOSE:
                            print(job.name + ': Finish at {0:.2f}, trnd_t = {1:.2f}, wait_t = {2:.2f}' \
                                .format(finishTime, job.trnd_t, job.wait_t))
                            print('{0:.2f} Number of jobs in the system at the time a job finished: {1:d}'.format(env.now,queueLength - 1))
                        
                else:
                    self.jobServing -= 1
                    job.allotment -= pass_time
                    job.remain_t -= pass_time
                    self.queue_1.append(job)
    # End handle_queue_1
    
    def handle_queue_2(self, job):    
        #print("Enter handle 2")
        with self.cpu.request(priority = job.priority) as req:
            try:
                yield req 
            except simpy.Interrupt as interrupt:
                return 0
            try:
                job.trigger_event_source.succeed()
                job.trigger_event_source = simpy.Event(env)
                current_time = self.env.now
                if job.io:
                    self.env.process(self.generate_io(job))
                self.jobServing += 1

                if job.first_response:
                    self.jobsTotal += 1
                    current_t = self.env.now
                    self.first_responsetime += (current_t - job.arrtime)
                    job.first_response = 0
                    if VERBOSE:
                        print("{0:.2f} {1:s} first response time: {2:.2f}".format(env.now, job.name, env.now - job.arrtime))
                    """ if the job is stopped (quantum expired)"""
                if job.remain_t > job.allotment:
                    if VERBOSE:
                        print('Queued 2: ')
                        for i in range(len(self.queue_2)):
                            print(self.queue_2[i].name, end=" | ")
                        print('\n')
                        print('{0:.2f} serving:{1:s} | arr_t = {2:.2f} | l = {3:.2f}' \
                            .format(env.now, job.name, job.arrtime, job.remain_t))
                    timeout_event = self.env.timeout(job.allotment)
                    result = yield timeout_event | job.processing_job
                    if timeout_event not in result:
                        #print(env.now)
                        #print('aaaaaaaaaaaaaaaaa')
                        job.remain_t -= (env.now - current_time)
                        job.allotment -= (env.now - current_time)
                        self.jobServing -= 1
                        job.past_queue = 2
                        return
                    job.processing.succeed()
                    job.processing = simpy.Event(self.env)
                    job.remain_t = job.remain_t - job.allotment
                    job.allotment = job.remain_t
                    job.priority += 1
                    self.jobServing -= 1
                    self.queue_3.append(job)
                    if not self.serversleeping.triggered:
                        self.serversleeping.interrupt( 'Wake up, please.' )
                elif job.remain_t == job.allotment:
                    if VERBOSE:
                        print('Queued 2: ')
                        for i in range(len(self.queue_2)):
                            print(self.queue_2[i].name, end=" | ")
                        print('\n')
                        print('{0:.2f} serving:{1:s} | arr_t = {2:.2f} | l = {3:.2f}' .format(self.env.now, job.name, job.arrtime, job.remain_t))
                    timeout_event = self.env.timeout(job.remain_t)
                    result = yield timeout_event | job.processing_job
                    if timeout_event not in result:
                        #print(env.now)
                        #print('aaaaaaaaaaaaaaaaa')
                        job.remain_t -= (env.now - current_time)
                        job.allotment -= (env.now - current_time)
                        self.jobServing -= 1
                        job.past_queue = 2
                        return
                    job.processing.succeed()
                    job.processing = simpy.Event(self.env)
                    self.jobServing -= 1
                    ''' for calculating mean of job in system'''
                    ''' right before the job leaves          '''
                    ''' like 2 2 2 2 2 2 1                   '''
                    ''' mark at this   ^                     '''
                    elapse = self.env.now - self.timeStamp
                    queueLength = len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + len(self.io_queue) + self.jobServing + 1
                    self.numJobsWithTimes.append((queueLength)*(elapse))
                    self.jobsInSysCount.append(queueLength)
                    self.jobsInSysCount_t.append(env.now)
                    self.timeStamp = self.env.now
                    finishTime = env.now
                    job.wait_t = finishTime - job.arrtime - job.service_t
                    job.trnd_t = finishTime - job.arrtime
                    self.waitingTime += job.wait_t
                    self.serviceTime += job.service_t
                    self.turnaroundTime += job.trnd_t
                    self.jobsDone += 1
                    if VERBOSE:
                        print(job.name + ': Finish at {0:.2f}, trnd_t = {1:.2f}, wait_t = {2:.2f}' \
                            .format(finishTime, job.trnd_t, job.wait_t))
                        print('{0:.2f} Number of jobs in the system at the time a job finished: {1:d}'.format(env.now,queueLength - 1))
            except simpy.Interrupt as interrupt:
                #print(interrupt)
                job.processing.succeed() 
                job.processing = simpy.Event(self.env)
                pass_time = env.now - current_time
                if VERBOSE:
                    print('Queued 2: ')
                    for i in range(len(self.queue_2)):
                        print(self.queue_2[i].name, end=" | ")
                    print('\n')
                    print('{0:s} is preempted at {1:.2f}. The remaining allotment is {2:.2f}'.format(job.name, env.now, job.remain_t - pass_time))
                if env.now - current_time == job.allotment:
                    if job.remain_t > job.allotment:
                        job.remain_t = job.remain_t - job.allotment
                        job.allotment = job.remain_t
                        job.priority += 1
                        self.jobServing -= 1
                        self.queue_3.append(job)
                        if not self.serversleeping.triggered:
                            self.serversleeping.interrupt( 'Wake up, please.' )
                    elif job.remain_t == job.allotment:
                        self.jobServing -= 1
                        elapse = self.env.now - self.timeStamp
                        queueLength = len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + len(self.io_queue) + self.jobServing + 1
                        self.numJobsWithTimes.append((queueLength)*(elapse))
                        self.jobsInSysCount.append(queueLength)
                        self.jobsInSysCount_t.append(env.now)
                        self.timeStamp = self.env.now
                        finishTime = env.now
                        job.wait_t = finishTime - job.arrtime - job.service_t
                        job.trnd_t = finishTime - job.arrtime
                        self.waitingTime += job.wait_t
                        self.serviceTime += job.service_t
                        self.turnaroundTime += job.trnd_t
                        self.jobsDone += 1
                        if VERBOSE:
                            print(job.name + ': Finish at {0:.2f}, trnd_t = {1:.2f}, wait_t = {2:.2f}' \
                                .format(finishTime, job.trnd_t, job.wait_t))
                            print('{0:.2f} Number of jobs in the system at the time a job finished: {1:d}'.format(self.env.now,queueLength - 1))
                else:
                    self.jobServing -= 1
                    job.allotment -= pass_time
                    job.remain_t -= pass_time
                    self.queue_2.append(job)
    def handle_queue_3(self, job):   
        #print("Enter handle 3")
        
        with self.cpu.request(priority = job.priority) as req:
            try:
                yield req 
            except simpy.Interrupt as interrupt:
                return 0
            try:
                job.trigger_event_source.succeed()
                job.trigger_event_source = simpy.Event(env)
                current_time = self.env.now
                self.jobServing += 1
                if job.io:
                    self.env.process(self.generate_io(job))

                if job.first_response:
                    self.jobsTotal += 1
                    current_t = self.env.now
                    self.first_responsetime += (current_t - job.arrtime)
                    job.first_response = 0
                    if VERBOSE:
                        print("{0:.2f} {1:s} first response time: {2:.2f}".format(env.now, job.name, env.now - job.arrtime))
                    """ if the job is stopped (quantum expired)"""
                if job.remain_t > job.allotment:
                    if VERBOSE:
                        print('Queued 3: ')
                        for i in range(len(self.queue_3)):
                            print(self.queue_3[i].name, end=" | ")
                        print('\n')
                        print('{0:.2f} serving:{1:s} | arr_t = {2:.2f} | l = {3:.2f}' \
                            .format(self.env.now, job.name, job.arrtime, job.remain_t))
                    timeout_event = self.env.timeout(job.allotment)
                    result = yield timeout_event | job.processing_job
                    if timeout_event not in result:
                        #print(env.now)
                        #print('aaaaaaaaaaaaaaaaa')
                        job.remain_t -= (env.now - current_time)
                        job.allotment -= (env.now - current_time)
                        self.jobServing -= 1
                        job.past_queue = 3
                        return
                    job.processing.succeed()
                    job.processing = simpy.Event(self.env)
                    
                    job.remain_t = job.remain_t - job.allotment
                    job.allotment = job.remain_t
                    job.priority += 1
                    self.jobServing -= 1
                    self.queue_3.append(job)
                    if not self.serversleeping.triggered:
                        self.serversleeping.interrupt( 'Wake up, please.' )
                elif job.remain_t == job.allotment:
                    if VERBOSE:
                        print('Queued 3: ')
                        for i in range(len(self.queue_3)):
                            print(self.queue_3[i].name, end=" | ")
                        print('\n')
                        print('{0:.2f} serving:{1:s} | arr_t = {2:.2f} | l = {3:.2f}' .format(env.now, job.name, job.arrtime, job.remain_t))
                
                    timeout_event = self.env.timeout(job.remain_t)
                    result = yield timeout_event  | job.processing_job
                    if timeout_event not in result:
                        #print(env.now)
                        #print('aaaaaaaaaaaaaaaaa')
                        job.remain_t -= (env.now - current_time)
                        job.allotment -= (env.now - current_time)
                        self.jobServing -= 1
                        job.past_queue = 3
                        return
                    job.processing.succeed()
                    job.processing = simpy.Event(self.env)
                    
                    self.jobServing -= 1
                    ''' for calculating mean of job in system'''
                    ''' right before the job leaves          '''
                    ''' like 2 2 2 2 2 2 1                   '''
                    ''' mark at this   ^                     '''
                    
                    
                    
                    elapse = self.env.now - self.timeStamp
                    queueLength = len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + len(self.io_queue) + self.jobServing + 1
                    self.numJobsWithTimes.append((queueLength)*(elapse))
                    self.jobsInSysCount.append(queueLength)
                    self.jobsInSysCount_t.append(env.now)
                    self.timeStamp = self.env.now
                    finishTime = env.now
                    job.wait_t = finishTime - job.arrtime - job.service_t
                    job.trnd_t = finishTime - job.arrtime
                    self.waitingTime += job.wait_t
                    self.serviceTime += job.service_t
                    self.turnaroundTime += job.trnd_t
                    self.jobsDone += 1
                    if VERBOSE:
                        print(job.name + ': Finish at {0:.2f}, trnd_t = {1:.2f}, wait_t = {2:.2f}' \
                            .format(finishTime, job.trnd_t, job.wait_t))
                        print('{0:.2f} Number of jobs in the system at the time a job finished: {1:d}'.format(self.env.now,queueLength - 1))
            except simpy.Interrupt as interrupt:
                #print(interrupt)
                job.processing.succeed()
                job.processing = simpy.Event(self.env)
                pass_time = env.now - current_time
                if VERBOSE:
                    print('Queued 3: ')
                    for i in range(len(self.queue_3)):
                        print(self.queue_3[i].name, end=" | ")
                    print('\n')
                    print('{0:s} is preempted at {1:.2f}. The remaining allotment is {2:.2f}'.format(job.name, env.now, job.remain_t - pass_time))
                if env.now - current_time == job.allotment:
                    if job.remain_t > job.allotment:
                        job.remain_t = job.remain_t - job.allotment
                        job.allotment = job.remain_t
                        job.priority += 1
                        self.jobServing -= 1
                        self.queue_3.append(job)
                        if not self.serversleeping.triggered:
                            self.serversleeping.interrupt( 'Wake up, please.' )
                    elif job.remain_t == job.allotment:
                        self.jobServing -= 1
                        elapse = self.env.now - self.timeStamp
                        queueLength = len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + len(self.io_queue) + self.jobServing + 1
                        self.numJobsWithTimes.append((queueLength)*(elapse))
                        self.jobsInSysCount.append(queueLength)
                        self.jobsInSysCount_t.append(env.now)
                        self.timeStamp = self.env.now
                        finishTime = env.now
                        job.wait_t = finishTime - job.arrtime - job.service_t
                        job.trnd_t = finishTime - job.arrtime
                        self.waitingTime += job.wait_t
                        self.serviceTime += job.service_t
                        self.turnaroundTime += job.trnd_t
                        self.jobsDone += 1
                        if VERBOSE:
                            print(job.name + ': Finish at {0:.2f}, trnd_t = {1:.2f}, wait_t = {2:.2f}' \
                                .format(finishTime, job.trnd_t, job.wait_t))
                            print('{0:.2f} Number of jobs in the system at the time a job finished: {1:d}'.format(self.env.now,queueLength - 1))    
                else:
                    self.jobServing -= 1
                    job.allotment -= pass_time
                    job.remain_t -= pass_time
                    self.queue_3.append(job)
    def generate_io(self, job):
        current_time = env.now
        io_interarrival = (random.exponential(1/job.lam_io))
        timeout_event = self.env.timeout(io_interarrival)
        result = yield timeout_event | job.processing
        if timeout_event not in result:
            #print(env.now)
            #print('aaaaaaaaaaaaaaaaa1')
            return
        job.processing_job.succeed()
        job.processing_job = simpy.Event(self.env)
        job.io_arrtime = self.env.now
        job.io_service_t = (random.exponential(1/job.mu_io))
        self.io_queue.append(job)
        if VERBOSE:
            print('{0:.2f} IO request: {1:s} | inter-arr_t = {2:.2f} | l = {3:.2f}' \
                .format(self.env.now, job.name, job.io_arrtime , job.io_service_t))
        if not self.server_io_request.triggered:
            self.server_io_request.interrupt()
    def waiting(self, env):
        try:
            if VERBOSE:
                print( 'Server is idle at %.2f' % self.env.now )
            yield self.env.timeout( MAXSIMTIME )
        except simpy.Interrupt as i:
            if VERBOSE:
                 print('Server waken up and works at %.2f' % self.env.now )
    def waiting_io(self, env):
        try:
            yield self.env.timeout( MAXSIMTIME )
        except simpy.Interrupt as i:
            if VERBOSE:
                print("IO request at %.2f" % self.env.now)
    def timeout(self):
        while True:
            yield self.env.timeout(100)
            for job in self.queue_2:
                job.priority = 1
            for job in self.queue_3:
                job.priority = 1
            self.queue_1 = self.queue_3 + self.queue_2 + self.queue_1
            self.queue_2.clear()
            self.queue_3.clear()
            if VERBOSE:
                print("TIME OUT !!!")
                print('Number of jobs in the sys: {0:d}' .format(len(self.queue_1) + len(self.queue_2) + len(self.queue_3) + self.jobServing))
                print('Queued 1: ')
                for i in range(len(self.queue_1)):
                        print(self.queue_1[i].name, end=" | ")
                print('\n')
                print('Queued 2: ')
                for i in range(len(self.queue_2)):
                        print(self.queue_2[i].name, end=" | ")
                print('\n')
                print('Queued 3: ')
                for i in range(len(self.queue_3)):
                        print(self.queue_3[i].name, end=" | ")
                print('\n')

class JobGenerator:
    def __init__(self, env, server, nrjobs = 10000000, lam = 5, mu = 6, lam_io = 8, mu_io = 8, io_probability=0.3):
        self.server = server
        self.nrjobs = nrjobs
        self.interarrivaltime = 1/lam
        self.servicetime = 1/mu
        env.process(self.generatejobs(env) )
        env.process(self.job_log(env))
        self.lam_io = lam_io
        self.mu_io = mu_io 
        self.io_probability = io_probability

    def generatejobs(self, env):
        i = 1
        while True:
            ''' yield an event for new job arrival'''
            job_interarrival = (random.exponential( self.interarrivaltime ))
            yield env.timeout( job_interarrival )

            ''' for calculate mean number of job in system'''
            ''' before the job come                       '''
            ''' like  0 0 0 0 0 1                         '''
            ''' mark at this  ^                           '''
            elapse = env.now-self.server.timeStamp
            queueLength = len(self.server.queue_1) +len(self.server.queue_2)+len(self.server.queue_3) + len(self.server.io_queue) + self.server.jobServing
            self.server.numJobsWithTimes.append((queueLength)*(elapse))
            self.server.jobsInSysCount.append(queueLength)
            self.server.jobsInSysCount_t.append(env.now)
            self.server.timeStamp = env.now

            ''' generate service time and add job to the list'''
            job_duration = (random.exponential( self.servicetime))
            io = random.uniform(0, 1) < self.io_probability
            self.server.queue_1.append( Job(self.server, 'Job %s' %i, env.now, job_duration, job_duration, job_duration if job_duration < QUANTUM_QUEUE_1 else QUANTUM_QUEUE_1 , 1, 1, io, self.lam_io, self.mu_io) )

            if VERBOSE:
                print('{0:.2f} arrive: Job {1:d} | inter-arr_t = {2:.2f} | l = {3:.2f}' \
                    .format(env.now, i, job_interarrival, job_duration))
                print('{0:.2f} Number of job in the system is sampled at arrival:  {1:d}'.format(env.now,queueLength))
                print('Time elapsed form last sample:           {0:.2f}'.format(elapse))
            i += 1

            ''' if server is idle, wake it up'''
            if not self.server.serversleeping.triggered:
                self.server.serversleeping.interrupt( 'Wake up, please.' )

    def job_log(self, env):
        while True:
            if (len(self.server.queue_1) + len(self.server.queue_2) + len(self.server.queue_3) + len(self.server.io_queue) + self.server.jobServing) not in self.server.length:
                self.server.length.append(len(self.server.queue_1) + len(self.server.queue_2) + len(self.server.queue_3) + len(self.server.io_queue) + self.server.jobServing)
            self.server.job_in_sys_count.append(len(self.server.queue_1) + len(self.server.queue_2) + len(self.server.queue_3) + len(self.server.io_queue) + self.server.jobServing)
            yield env.timeout(1)

# env = simpy.Environment()
# MyServer = Server( env )
# MyJobGenerator = JobGenerator( env, MyServer, POPULATION, LAMBDA, MU, LAMBDA_IO, MU_IO, IO_PROBALITIES)

# ''' start simulation '''
# env.run( until = 400)

#######################################
# LAMBDA A
# MU B
# LAMBDA_IO C
# MU_IO D
# IO_PROBALITIES E
# QUANTUM_QUEUE_1 F
# QUANTUM_QUEUE_2 G

if EXPERIMENT:
    turnaroundTime_exp = []
    waiting_exp = []
    mean_job_exp = []
    idle_exp = []
    first_response_exp = []
    for i in range(8):
        if i == 0:
            LAMBDA = lambda_exp[0]
            MU = mu_exp[0]
            LAMBDA_IO = lambda_io_exp[0]
            MU_IO = mu_io_exp[1]
            IO_PROBALITIES = io_probalities_exp[1]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[1]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[0]
        elif i == 1:
            LAMBDA = lambda_exp[1]
            MU = mu_exp[0]
            LAMBDA_IO = lambda_io_exp[0]
            MU_IO = mu_io_exp[0]
            IO_PROBALITIES = io_probalities_exp[0]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[1]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[1]
        elif i == 2:
            LAMBDA = lambda_exp[0]
            MU = mu_exp[1]
            LAMBDA_IO = lambda_io_exp[0]
            MU_IO = mu_io_exp[0]
            IO_PROBALITIES = io_probalities_exp[1]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[0]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[1]
        elif i == 3:
            LAMBDA = lambda_exp[1]
            MU = mu_exp[1]
            LAMBDA_IO = lambda_io_exp[0]
            MU_IO = mu_io_exp[1]
            IO_PROBALITIES = io_probalities_exp[0]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[0]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[0]
        elif i == 4:
            LAMBDA = lambda_exp[0]
            MU = mu_exp[0]
            LAMBDA_IO = lambda_io_exp[1]
            MU_IO = mu_io_exp[1]
            IO_PROBALITIES = io_probalities_exp[0]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[0]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[1]
        elif i == 5:
            LAMBDA = lambda_exp[1]
            MU = mu_exp[0]
            LAMBDA_IO = lambda_io_exp[1]
            MU_IO = mu_io_exp[0]
            IO_PROBALITIES = io_probalities_exp[1]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[0]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[0]
        elif i == 6:
            LAMBDA = lambda_exp[0]
            MU = mu_exp[1]
            LAMBDA_IO = lambda_io_exp[1]
            MU_IO = mu_io_exp[0]
            IO_PROBALITIES = io_probalities_exp[0]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[1]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[0]
        elif i == 7:
            LAMBDA = lambda_exp[1]
            MU = mu_exp[1]
            LAMBDA_IO = lambda_io_exp[1]
            MU_IO = mu_io_exp[1]
            IO_PROBALITIES = io_probalities_exp[1]
            QUANTUM_QUEUE_1 = quantum_queue_1_exp[1]
            QUANTUM_QUEUE_2 = quantum_queue_2_exp[1]
        meanJobDone = []
        meanUtilization = []
        meanWaitingTime = []
        meanServiceTime = []
        meanturnaroundTime = []
        meanSysIdleTime = []
        meanJobInSystem = []
        meanFirstResponseTime = []
        for j in range(NSIM):
            env = simpy.Environment()
            MyServer = Server(env)
            MyJobGenerator = JobGenerator( env, MyServer, POPULATION, LAMBDA, MU, LAMBDA_IO, MU_IO, IO_PROBALITIES)
            env.run(until=MAXSIMTIME)
            meanJobDone.append(MyServer.jobsDone)
            meanUtilization.append(1-MyServer.idleTime/MAXSIMTIME)
            meanWaitingTime.append(MyServer.waitingTime/MyServer.jobsDone)
            meanServiceTime.append(MyServer.serviceTime/MyServer.jobsDone)
            meanturnaroundTime.append(MyServer.turnaroundTime/MyServer.jobsDone)
            meanSysIdleTime.append(MyServer.idleTime)
            last = (len(MyServer.queue_1) + len(MyServer.queue_2) + len(MyServer.queue_3) + len(MyServer.io_queue))*(MAXSIMTIME-MyServer.jobsInSysCount_t[-1])
            meanJobInSystem.append((sum(MyServer.numJobsWithTimes)+last)/MAXSIMTIME)
            meanFirstResponseTime.append(MyServer.first_responsetime/MyServer.jobsTotal)
        mean_job_res = sum(meanJobDone)/NSIM
        utilization_res = sum(meanUtilization)/NSIM
        idle_exp.append(1 - utilization_res)
        waiting_res = sum(meanWaitingTime)/NSIM
        waiting_exp.append(waiting_res)
        response_res = sum(meanturnaroundTime)/NSIM
        turnaroundTime_exp.append(response_res)
        meanJobInSys = sum(meanJobInSystem)/NSIM
        mean_job_exp.append(meanJobInSys)
        
        first_response_res = sum(meanFirstResponseTime)/NSIM
        first_response_exp.append(first_response_res)
    A = np.array([[1.,-1., -1.,  -1., 1.,  1.,  1., -1.],
                [1., 1., -1. , -1., -1., -1.,  1.,  1.],
                [1., -1.,  1., -1., -1.,  1., -1.,  1.],
                [1.,  1.,  1.,  -1., 1., -1., -1., -1.],
                [1., -1., -1.,  1.,  1., -1., -1.,  1.],
                [1., 1., -1., 1.,  -1.,  1., -1., -1.],
                [1., -1.,  1., 1.,  -1., -1.,  1., -1.],
                [1., 1.,  1.,  1.,  1.,  1.,  1.,  1.]])
    B = np.linalg.inv(A)
    turnaroundTime_index = B.dot(turnaroundTime_exp)
    waiting_index = B.dot(waiting_exp)
    mean_job_index = B.dot(mean_job_exp)
    idle_index = B.dot(idle_exp)

    first_response_index = B.dot(first_response_exp)

    print("\nTurnaround time index and impact solution from result of experiments")
    impact = []
    variation = []
    mean_turnaround = sum(turnaroundTime_exp)/8
    SST = sum([(i - mean_turnaround)*(i - mean_turnaround) for i in turnaroundTime_exp])
    variation.append(0)
    for i in range(1, len(turnaroundTime_index)):
        variation.append(8*turnaroundTime_index[i]* turnaroundTime_index[i])
    variation.append(SST)
    for i in variation:
        impact.append(i/SST)
    turnaroundTime_index = append(turnaroundTime_index,1)

    pd1 = pd.DataFrame({'I':A[:,0],'A':A[:,1],'B':A[:,2],'C':A[:,3],'D':A[:,4],'E':A[:,5],'F':A[:,6],'G':A[:,7],'Response Time':turnaroundTime_exp})
    pd1.loc[len(pd1)] = turnaroundTime_index
    pd1.loc[len(pd1)] = variation
    pd1.loc[len(pd1)] = impact
    pd1 = pd1.round({'I':2,'A':2,'B':2,'C':2,'D':2,'E':2,'F':2,'G':2,'Response Time':2})
    pd1 = pd1.rename(index={8: 'Index',9: 'Variation', 10:'Fraction'})
    print(pd1)    

    print("\nFirst Response time index and impact solution from result of experiments")

    impact = []
    variation = []
    mean_first_response = sum(first_response_exp)/8
    SST = sum([(i - mean_first_response)*(i - mean_first_response) for i in first_response_exp])
    variation.append(0)
    for i in range(1, len(first_response_index)):
        variation.append(8*first_response_index[i]* first_response_index[i])
    variation.append(SST)
    for i in variation:
        impact.append(i/SST)
    first_response_index = append(first_response_index,1)

    pd1 = pd.DataFrame({'I':A[:,0],'A':A[:,1],'B':A[:,2],'C':A[:,3],'D':A[:,4],'E':A[:,5],'F':A[:,6],'G':A[:,7],'First Response Time':first_response_exp})
    pd1.loc[len(pd1)] = first_response_index
    pd1.loc[len(pd1)] = variation
    pd1.loc[len(pd1)] = impact
    pd1 = pd1.round({'I':2,'A':2,'B':2,'C':2,'D':2,'E':2,'F':2,'G':2,'First Response Time':2})
    pd1 = pd1.rename(index={8: 'Index',9: 'Variation', 10:'Fraction'})
    print(pd1)


    print("\n\nWaiting time index and impact solution from result of experiments")
    impact = []
    variation = []
    mean_waiting = sum(waiting_exp)/8
    SST = sum([(i - mean_waiting)*(i - mean_waiting) for i in waiting_exp])
    variation.append(0)
    for i in range(1, len(waiting_index)):
        variation.append(8*waiting_index[i]* waiting_index[i])
    variation.append(SST)
    for i in variation:
        impact.append(i/SST)
    waiting_index = append(waiting_index,1)
    
    pd1 = pd.DataFrame({'I':A[:,0],'A':A[:,1],'B':A[:,2],'C':A[:,3],'D':A[:,4],'E':A[:,5],'F':A[:,6],'G':A[:,7],'Waiting Time':waiting_exp})
    pd1.loc[len(pd1)] = waiting_index
    pd1.loc[len(pd1)] = variation
    pd1.loc[len(pd1)] = impact
    pd1 = pd1.round({'I':2,'A':2,'B':2,'C':2,'D':2,'E':2,'F':2,'G':2,'Waiting Time':2})
    pd1 = pd1.rename(index={8: 'Index',9: 'Variation', 10:'Fraction'})
    print(pd1)

    print("\n\nMean job index and impact solution from result of experiments")
    impact = []
    variation = []
    mean_job = sum(mean_job_exp)/8
    SST = sum([(i - mean_job)*(i - mean_job) for i in mean_job_exp])
    variation.append(0)
    for i in range(1, len(mean_job_index)):
        variation.append(8*mean_job_index[i]* mean_job_index[i])
    variation.append(SST)
    for i in variation:
        impact.append(i/SST)
    mean_job_index = append(mean_job_index,1)

    pd1 = pd.DataFrame({'I':A[:,0],'A':A[:,1],'B':A[:,2],'C':A[:,3],'D':A[:,4],'E':A[:,5],'F':A[:,6],'G':A[:,7],'Mean Job':mean_job_exp})
    pd1.loc[len(pd1)] = mean_job_index
    pd1.loc[len(pd1)] = variation
    pd1.loc[len(pd1)] = impact
    pd1 = pd1.round({'I':2,'A':2,'B':2,'C':2,'D':2,'E':2,'F':2,'G':2,'Mean Job':2})
    pd1 = pd1.rename(index={8: 'Index',9: 'Variation', 10:'Fraction'})
    print(pd1)


    print("\n\nIdle Time index and impact solution from result of experiments")
    impact = []
    variation = []
    mean_idle = sum(idle_exp)/8
    SST = sum([(i - mean_idle)*(i - mean_idle) for i in idle_exp])
    variation.append(0)
    for i in range(1, len(idle_index)):
        variation.append(8*idle_index[i]* idle_index[i])
    variation.append(SST)
    for i in variation:
        impact.append(i/SST)
    idle_index = append(idle_index,1)
    pd1 = pd.DataFrame({'I':A[:,0],'A':A[:,1],'B':A[:,2],'C':A[:,3],'D':A[:,4],'E':A[:,5],'F':A[:,6],'G':A[:,7],'Idle Time':idle_exp})
    pd1.loc[len(pd1)] = idle_index
    pd1.loc[len(pd1)] = variation
    pd1.loc[len(pd1)] = impact
    pd1 = pd1.round({'I':2,'A':2,'B':2,'C':2,'D':2,'E':2,'F':2,'G':2,'Idle Time':2})
    pd1 = pd1.rename(index={8: 'Index',9: 'Variation', 10:'Fraction'})
    print(pd1)

if SIMULATE:
    ''' start SimPy environment '''
    env = simpy.Environment()
    MyServer = Server( env)
    MyJobGenerator = JobGenerator( env, MyServer, POPULATION, LAMBDA, MU, LAMBDA_IO, MU_IO, IO_PROBALITIES)

    ''' start simulation '''
    env.run( until = MAXSIMTIME )

    ''' print statistics '''
    RHO = LAMBDA/MU
    print('Job Done:                                    : {0:d}' .format(MyServer.jobsDone))               
    print('Utilization                                  : {0:.2f}/{1:.2f}' .format(1-MyServer.idleTime/MAXSIMTIME,RHO))
    try:
        print('Mean waiting time                            : {0:.2f}'.format(MyServer.waitingTime/MyServer.jobsDone))
    except ZeroDivisionError:
        print('No job has been done')
    try:
        print('Mean service time                            : {0:.2f}'.format(MyServer.serviceTime/MyServer.jobsDone))
    except ZeroDivisionError:
        print('No job has been done')
    try:
        print('Turn around time                           : {0:.2f}'.format(MyServer.turnaroundTime/MyServer.jobsDone))
    except ZeroDivisionError:
        print('No job has been done')
    try:
        print('Mean first response time                     : {0:.2f}'.format(MyServer.first_responsetime/MyServer.jobsTotal))
    except ZeroDivisionError:
        print('No job has been done')
    print('System idle time                             : {0:.2f}' .format(MyServer.idleTime))
    try:
        last = (len(MyServer.queue_1) + len(MyServer.queue_2) + len(MyServer.queue_3) + len(MyServer.io_queue))*(MAXSIMTIME-MyServer.jobsInSysCount_t[-1])
        mean_job_in_sys = (sum(MyServer.numJobsWithTimes)+last)/MAXSIMTIME
        print('Mean job in system                           : {0:.2f}' .format(mean_job_in_sys))
    except ZeroDivisionError:
        print('No job has been done')
    print('Variance of job in system                    : {0:.4f}' .format(float(statistics.variance(MyServer.jobsInSysCount))))
    sd = float(statistics.stdev(MyServer.jobsInSysCount))
    print('Standard deviation of job in system          : {0:.4f}' .format(sd)) 
    ''' With the confidence level value z = 1.96 (95%)'''
    num_observe = len(MyServer.numJobsWithTimes) + 1
    print('Confidence interval of mean job in the system: [{0:.4f}, {1:.4f}]' .format( mean_job_in_sys - 1.96*sd/sqrt(num_observe), mean_job_in_sys + 1.96*sd/sqrt(num_observe) ))

    ''' Graphs plotting '''
    fig, plt1 = plt.subplots(1)
    plt1.set_title("Number of jobs in system overtime")
    plt1.set(xlabel='Time', ylabel='Jobs')
    plt1.plot(MyServer.jobsInSysCount_t, MyServer.jobsInSysCount)

    plt1.vlines(0, plt.ylim()[0], plt.ylim()[1], linestyles='dashed')
    plt.show()










        

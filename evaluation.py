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
#Multiple simulations to get mean value 
MULTIPLE_SIMULATION = False
#Again, multiple simulations for experiments
EXPERIMENT = True
# Experiment running for the QUANTUM effect
EXPERIMENT_QUANTUM_On_FIRST_RESPONSE = False
''' ------------------------ '''
''' Experiment list          '''
''' 2 level only              '''
''' ------------------------ '''
lambda_exp = [0.025, 0.05]
mu_exp = [0.1, 0.2]
quantum_exp = [0.3, 3]
''' ------------------------ '''
''' Parameters               '''
''' ------------------------ '''
MAXSIMTIME = 1000000
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
VERBOSE = True
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
         - SJF : Shortest Job First
         - RR: Round-robin
'''
class Server:
    def __init__(self, env, strat = 'RR'):
        self.env = env
        """ Create resources """
        self.cpu = simpy.PreemptiveResource(env, capacity = NUM_CPU)
        """ Create resources """
 
        
        self.strat = strat
        self.queue_1 = []
        self.queue_2 = []
        self.queue_3 = []
        self.io_queue = []
        self.jobServing = 0
        
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
                yield self.serversleeping
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
        print("Enter handle 1")
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
                if LOGGED:
                    qlog.write( '%.4f\t%d\t%d\n' % (self.env.now, 1 if len(self.queue_1)>0 else 0, len(self.queue_1)) )
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
        print("Enter handle 2")
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
                if LOGGED:
                    qlog.write( '%.4f\t%d\t%d\n' % (self.env.now, 1 if len(self.queue_2)>0 else 0, len(self.queue_2)) )
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
        print("Enter handle 3")
        
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
                if LOGGED:
                    qlog.write( '%.4f\t%d\t%d\n' % (self.env.now, 1 if len(self.queue_3)>0 else 0, len(self.queue_3)) )
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
            if (len(self.server.queue_1) + len(self.server.queue_2) + len(self.server.queue_3) + self.server.jobServing) not in self.server.length:
                self.server.length.append(len(self.server.queue_1) + len(self.server.queue_2) + len(self.server.queue_3) + self.server.jobServing)
            self.server.job_in_sys_count.append(len(self.server.queue_1) + len(self.server.queue_2) + len(self.server.queue_3) + self.server.jobServing)
            yield env.timeout(1)
env = simpy.Environment()
MyServer = Server( env, SERVICE_DISCIPLINE )
MyJobGenerator = JobGenerator( env, MyServer, POPULATION, LAMBDA, MU, LAMBDA_IO, MU_IO, IO_PROBALITIES)

''' start simulation '''
env.run( until = 400)

import concurrent.futures,json,pathlib,tempfile,threading,time,unittest
from async_engine import Engine
from gateway import Gateway

class QueueTests(unittest.TestCase):
    def test_pending_call_never_blocks_barriers_and_deduplicates(self):
        release=threading.Event()
        def execute(call,committed=False):release.wait(3);return {'ok':True,'output':'42'}
        e=Engine(execute);call={'name':'read_file','args':{'path':'x'}}
        obs=[{'anchor':'a','call':call,'committed':False},{'anchor':'b','call':call,'committed':False}]
        try:
            start=time.perf_counter()
            for step in range(100):self.assertEqual(e.barrier(obs,step),[])
            self.assertLess(time.perf_counter()-start,.2);self.assertEqual(e.calls,1)
            release.set();e.close();self.assertEqual(len(e.barrier(obs,100)),2)
        finally:release.set();e.close()
    def test_revised_read_result_is_discarded(self):
        release=threading.Event()
        def execute(call,committed=False):release.wait(3);return {'ok':True,'output':'stale'}
        e=Engine(execute)
        e.barrier([{'anchor':'a','call':{'name':'read_file','args':{'path':'old'}},'committed':False}],0)
        release.set();e.close();self.assertEqual(e.barrier([],1),[])
        self.assertTrue(any(x['type']=='stale_completion' for x in e.events))

class LinuxGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='syscall-test-',dir='workspace');self.root=pathlib.Path(self.tmp.name).resolve();self.g=Gateway(self.root)
        (self.root/'secret.txt').write_text('secret-7319')
    def tearDown(self):self.tmp.cleanup()
    def call(self,name,**args):return self.g.execute({'name':name,'args':args},committed=name in ('write_file','remove'))
    def test_seven_calls(self):
        self.assertEqual(self.call('read_file',path='secret.txt',offset=7,length=4)['output'],'7319')
        self.assertIn('secret.txt',self.call('list_dir',path='.')['output'])
        self.assertEqual(json.loads(self.call('stat',path='secret.txt')['output'])['size'],11)
        self.assertGreater(json.loads(self.call('clock')['output'])['unix_ns'],0)
        self.assertEqual(self.call('run',cmd=['python3','-c','print(sum(range(10)))'],timeout_ms=2000)['output'],'45\n')
        self.assertTrue(self.call('write_file',path='out.txt',data='done')['ok']);self.assertEqual((self.root/'out.txt').read_text(),'done')
        self.assertTrue(self.call('remove',path='out.txt')['ok']);self.assertFalse((self.root/'out.txt').exists())
    def test_isolated_writes_and_no_network(self):
        r=self.call('run',cmd=['python3','-c',"open('secret.txt','w').write('changed'); print('ok')"],timeout_ms=2000)
        self.assertTrue(r['ok']);self.assertEqual((self.root/'secret.txt').read_text(),'secret-7319')
        r=self.call('run',cmd=['python3','-c',"import socket;s=socket.socket();s.settimeout(.2);s.connect(('1.1.1.1',80))"],timeout_ms=1000)
        self.assertFalse(r['ok']);self.assertIn('Network is unreachable',r['stderr'])
    def test_errors_and_uncommitted_effect(self):
        self.assertFalse(self.call('read_file',path='../escape')['ok'])
        self.assertFalse(self.call('read_file',path='missing')['ok'])
        self.assertEqual(self.call('run',cmd=['python3','-c','import time;time.sleep(1)'],timeout_ms=20)['output'],'timeout')
        r=self.g.execute({'name':'write_file','args':{'path':'bad.txt','data':'bad'}},committed=False)
        self.assertFalse(r['ok']);self.assertFalse((self.root/'bad.txt').exists())
    def test_commit_rule_vs_unsafe_control(self):
        def observe(path,committed):return [{'anchor':'write','call':{'name':'write_file','args':{'path':path,'data':'x'}},'committed':committed}]
        guarded=Engine(self.g.execute)
        guarded.barrier(observe('guarded_bad.txt',False),0)
        guarded.barrier(observe('guarded_good.txt',False),1)
        self.assertFalse((self.root/'guarded_bad.txt').exists());self.assertFalse((self.root/'guarded_good.txt').exists())
        guarded.barrier(observe('guarded_good.txt',True),2);guarded.close()
        self.assertFalse((self.root/'guarded_bad.txt').exists());self.assertTrue((self.root/'guarded_good.txt').exists())
        self.assertTrue(any(x['type']=='dropped_effect' for x in guarded.events))
        unsafe=Engine(self.g.execute,commit_rule=False)
        unsafe.barrier(observe('unsafe_bad.txt',False),0)
        for job in unsafe.jobs:job['future'].result(timeout=12) # Test setup, outside denoising.
        unsafe.barrier(observe('unsafe_good.txt',False),1);unsafe.close()
        self.assertTrue((self.root/'unsafe_bad.txt').exists());self.assertTrue(any(x['type']=='stray_effect' for x in unsafe.events))
if __name__=='__main__':unittest.main()

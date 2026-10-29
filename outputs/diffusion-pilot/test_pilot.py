import unittest
from pilot import dataset,score,posthoc,EQ,calculate,MASK

class EvaluationTests(unittest.TestCase):
    def test_balanced_tasks(self):
        rows=dataset()
        self.assertEqual(len(rows),36)
        self.assertEqual(sum(r['expected']=='YES' for r in rows),9)
        self.assertEqual(sum(r['expected']=='NO' for r in rows),9)
        self.assertEqual(len({r['id'] for r in rows}),36)
    def test_posthoc_preserves_downstream_answer(self):
        text='123 * 456 = 999\nAnswer: NO'
        self.assertEqual(posthoc(text,'dependent'),'123 * 456 = 56088\nAnswer: NO')
    def test_posthoc_corrects_direct_answer(self):
        self.assertEqual(posthoc('123 * 456 = 999\nAnswer: 999'),'123 * 456 = 56088\nAnswer: 56088')
    def test_posthoc_replaces_complete_comma_span(self):
        self.assertEqual(posthoc('123 * 456 = 55,000\nAnswer: 55,000'),'123 * 456 = 56088\nAnswer: 56088')
    def test_no_oracle_fallback(self):
        self.assertEqual(posthoc('Answer: 999'),'Answer: 999')
    def test_strict_scoring(self):
        row=dataset()[0]
        self.assertFalse(score('Some number '+row['expected'],row)['correct'])
        self.assertTrue(score('Answer: '+row['expected'],row)['correct'])
    def test_parser_rejects_decimal_suffix(self):
        self.assertIsNone(EQ.search('12.34 * 5 ='))
    def test_signed_integer(self):
        m=EQ.search('-123 - -456 =')
        self.assertEqual(calculate(int(m['a']),m['op'],int(m['b'])),333)

if __name__=='__main__': unittest.main()

class HookTests(unittest.TestCase):
    def setUp(self):
        try: import torch
        except ImportError: self.skipTest('torch required for hook checks')
        self.torch=torch
        class Chars:
            def decode(self,ids,**kw):return ''.join(chr(x) for x in ids)
            def encode(self,text,**kw):return list(map(ord,text))
        self.tokenizer=Chars()
    def fixture(self,length=30):
        t=self.torch
        ids=list(map(ord,'12 * 34 ='))+[ord('x')]*(length-9)
        draft=t.tensor([ids]);x=t.full_like(draft,MASK);conf=t.ones_like(draft,dtype=t.float32)
        rows=[dict(id=0,a=99,b=99,op='*')]
        return x,draft,conf,rows
    def test_calculates_parsed_operands_not_oracle(self):
        from pilot import hook
        x,draft,conf,rows=self.fixture();events=[];done=[False]
        hook(self.tokenizer,x,draft,conf,0,rows,done,events,32,.5,backend='cpu')
        self.assertTrue(done[0]);self.assertEqual(events[0]['value'],'408');self.assertFalse(events[0]['operand_match'])
        self.assertEqual(self.tokenizer.decode(x[0,9:14].tolist()),' 408\n')
    def test_occupied_slot_is_not_overwritten(self):
        from pilot import hook
        x,draft,conf,rows=self.fixture();x[0,10]=ord('9');before=x.clone();events=[]
        hook(self.tokenizer,x,draft,conf,0,rows,[False],events,32,.5,backend='cpu')
        self.assertTrue(self.torch.equal(x,before));self.assertEqual(events[0]['status'],'occupied_slot')
    def test_short_slot_is_rejected(self):
        from pilot import hook
        x,draft,conf,rows=self.fixture(10);events=[]
        hook(self.tokenizer,x,draft,conf,0,rows,[False],events,32,.5,backend='cpu')
        self.assertEqual(events[0]['status'],'length_failure')

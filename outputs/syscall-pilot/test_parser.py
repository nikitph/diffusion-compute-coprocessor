import json,unittest
from call_parser import parse_tokens,validate
class Characters:
    def decode(self,ids,**kwargs):return ''.join(chr(i) for i in ids if i)
class ParserTests(unittest.TestCase):
    def test_padding_not_part_of_commit_span(self):
        text='{"name":"read_file","args":{"path":"x"}}';ids=list(map(ord,text))+[0]*8
        call,indices=parse_tokens(Characters(),ids)
        self.assertEqual(call['name'],'read_file');self.assertEqual(indices,list(range(len(text))))
    def test_incomplete_json_is_not_a_call(self):
        self.assertIsNone(parse_tokens(Characters(),list(map(ord,'{"name":"write_file"'))))
    def test_extra_text_rejected(self):
        self.assertIsNone(parse_tokens(Characters(),list(map(ord,'{"name":"clock"} garbage'))))
    def test_path_and_command_types(self):
        self.assertFalse(validate({'name':'read_file','args':{'path':'../outside'}}))
        self.assertFalse(validate({'name':'run','args':{'cmd':'echo hi'}}))
        self.assertTrue(validate({'name':'run','args':{'cmd':['python3','-c','print(1)']}}))
if __name__=='__main__':unittest.main()

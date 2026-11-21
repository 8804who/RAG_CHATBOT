# T-028 token-length check of stored chunks vs e5 512-token limit. Usage: python tok.py <S>/chunks_vec.json
import json,sys,statistics,re
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download
import glob,os
p=glob.glob('/Users/kimjuseong/Desktop/code/RAG_Chatbot/backend/app/.cache/fastembed/models--qdrant--multilingual-e5-large-onnx/snapshots/*/tokenizer.json')
p=[x for x in p if 'e5' in x.lower()]
print(p[:2])
tk=Tokenizer.from_file(p[0])
pts=json.load(open(sys.argv[1]))['result']['points']
L=[];over=0
for x in pts:
    n=len(tk.encode(x['payload']['text']).ids); L.append(n); over+= n>512
print('tokens/chunk median',statistics.median(L),'min',min(L),'max',max(L),'chunks>512',over,'/',len(L))
print('frac text beyond 512 tok (mean):', statistics.mean([max(0,n-512)/n for n in L]))
words=[len(x['payload']['text'].split()) for x in pts]; print('words median',statistics.median(words))
ws=[x['payload'].get('embedding_tokens') for x in pts][:5]; print('embedding_tokens sample',ws)

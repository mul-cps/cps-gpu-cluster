#!/usr/bin/env python3
import sys

def strip_crds(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    docs = content.split('---')
    new_docs = []
    
    for doc in docs:
        if not doc.strip():
            continue
            
        # Check if doc is a CRD
        lines = doc.strip().split('\n')
        is_crd = False
        for line in lines:
            if line.strip().startswith('kind: CustomResourceDefinition'):
                is_crd = True
                break
        
        if not is_crd:
            new_docs.append(doc)
            
    with open(file_path, 'w') as f:
        f.write('---\n'.join(new_docs))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 strip_crds.py <file_path>")
        sys.exit(1)
    
    strip_crds(sys.argv[1])

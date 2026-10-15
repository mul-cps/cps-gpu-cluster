#!/usr/bin/env python3
"""Generate a fail-closed pinned-source experimental patch; no module actions."""
import difflib
import hashlib

VERSION='615.71.09'
SOURCE_SHA256='cf8d21c77f7db22f11b1a9c80f4197644d736d145afc2ea01bf057f83faaf8af'
CALLER_SHA256='81870dad066249991b39e2f1e70ddf0a48e4803eb48f487d0de7708c835a621a'
STATUS_SHA256='4a9a39b51862d21cfa446414135386616a4a4914dd34dc83f98099295fea7b56'
MAKEFILE_SHA256='eec07e6dfc0d204af6f8a7c0dfc4af70a037bf92d61ec2b03166a242bf7536ec'
CORE_BINARY_SHA256='cf9b219820207251c18b166f26f14d0ad41a25e4e337954905a114dbd0986a21'
PARAMETER='''
// Experimental global canary guard. Load-time only; production use unqualified.
static bool uvm_deny_managed_mmap = false;
module_param(uvm_deny_managed_mmap, bool, 0444);
MODULE_PARM_DESC(uvm_deny_managed_mmap, "Experimental deny of new managed mmap ranges; default off");
'''
GUARD='''    if (uvm_deny_managed_mmap) {
        // Preserve collisions for the caller's exact semaphore/P2P fallback.
        if (uvm_range_tree_iter_first(&va_space->va_range_tree, vma->vm_start, vma->vm_end - 1) != NULL)
            return NV_ERR_UVM_ADDRESS_IN_USE;

        return NV_ERR_NOT_SUPPORTED;
    }

'''


def require(ok, message):
    if not ok:raise ValueError(message)


def verify(raw, expected):
    require(hashlib.sha256(raw).hexdigest()==expected,'Pinned original source hash mismatch')


def patched(raw):
    require(b'uvm_deny_managed_mmap' not in raw,'Already patched source refused')
    verify(raw,SOURCE_SHA256)
    text=raw.decode()
    include='#include <linux/sched.h>\n'
    anchor='    uvm_va_range_managed_t *managed_range = NULL;\n\n    // Check for no overlap with HMM blocks.\n'
    require(text.count(include)==1 and text.count(anchor)==1,'Unique pinned insertion anchors required')
    text=text.replace(include,include+PARAMETER,1)
    text=text.replace(anchor,'    uvm_va_range_managed_t *managed_range = NULL;\n\n'+GUARD+'    // Check for no overlap with HMM blocks.\n',1)
    return text.encode()


def patch_text(raw):
    return ''.join(difflib.unified_diff(raw.decode().splitlines(True),patched(raw).decode().splitlines(True),
                                      fromfile='a/nvidia-uvm/uvm_va_range.c',tofile='b/nvidia-uvm/uvm_va_range.c'))


def definition(text, signature):
    start=text.index(signature);brace=text.index('{',start);depth=0
    for index in range(brace,len(text)):
        if text[index]=='{':depth+=1
        elif text[index]=='}':
            depth-=1
            if depth==0:return text[start:index+1]
    raise ValueError('Complete pinned C definition required')

"""Extraction produces reviewable spans, never asserted graph facts."""
import os
import re
from functools import lru_cache


@lru_cache(maxsize=1)
def ner():
    from transformers import pipeline
    path = os.getenv('NER_MODEL_PATH')
    if not path:
        raise ValueError('Set NER_MODEL_PATH to a reviewed local token-classification model directory')
    return pipeline('token-classification', model=path, tokenizer=path,
                    aggregation_strategy='simple', device=-1, trust_remote_code=False)


def extract(text, mode='rules'):
    spans = []
    if mode == 'transformer':
        for e in ner()(text):
            spans.append({'text': text[e['start']:e['end']], 'start': e['start'], 'end': e['end'],
                          'kind': e['entity_group'], 'model_score': float(e['score'])})
    else:
        for kind, pattern in [('Email', r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),
                              ('Phone', r'(?<!\w)(?:\+91[- ]?)?[6-9]\d{9}\b'),
                              ('Date', r'\b\d{4}-\d{2}-\d{2}\b'),
                              ('Person', r'\bPerson [A-Z]\b')]:
            for m in re.finditer(pattern, text):
                spans.append({'text': m.group(), 'start': m.start(), 'end': m.end(), 'kind': kind})
    return {'mode': mode, 'spans': sorted(spans, key=lambda s: s['start']),
            'caveat': 'Mention extraction only. Does not infer identity, relations, truth or negation. Review in original context.'}

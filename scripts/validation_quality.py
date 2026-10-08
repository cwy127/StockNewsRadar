"""Shared, non-mutating eligibility rules for next-session performance."""
import math
from collections import Counter

PRICE_FIELDS = ('baseline_close', 'next_open', 'next_high', 'next_low', 'next_close')
RETURN_FIELDS = dict(zip(('gap_open_pct', 'next_high_pct', 'next_low_pct', 'next_close_pct'), PRICE_FIELDS[1:]))


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def price_errors(record):
    errors = [f'invalid_price:{field}' for field in PRICE_FIELDS
              if not finite_number(record.get(field)) or record[field] <= 0]
    if not errors:
        op, hi, lo, cl = (record[field] for field in PRICE_FIELDS[1:])
        if not (lo <= min(op, cl) <= max(op, cl) <= hi):
            errors.append('invalid_ohlc')
    return errors


def evaluation_errors(record):
    errors = price_errors(record)
    for field, price in RETURN_FIELDS.items():
        value = record.get(field)
        if not finite_number(value):
            errors.append(f'invalid_return:{field}')
        elif not price_errors(record):
            expected = round((record[price] / record['baseline_close'] - 1) * 100, 2)
            if not math.isfinite(expected) or abs(value - expected) > 0.011:
                errors.append(f'inconsistent_return:{field}')
    return errors


def partition_records(records):
    """Quarantine every ambiguous duplicate, with source indexes for auditability."""
    def key(row):
        return (row.get('signal_date'), str(row.get('symbol', '')).upper(), row.get('rank'))
    counts = Counter(key(row) for row in records if row.get('status') == 'evaluated')
    valid, excluded = [], []
    for index, row in enumerate(records):
        if row.get('status') not in ('evaluated', 'invalid'):
            continue
        reasons = evaluation_errors(row)
        if row.get('status') == 'invalid':
            reasons = reasons or ['invalid_status']
        if counts[key(row)] > 1:
            reasons.append('duplicate_evaluation')
        if reasons:
            excluded.append({'source_index': index, 'reasons': reasons, 'record': row})
        else:
            valid.append(row)
    return valid, excluded


def quality_summary(records, valid, excluded):
    return {'input_record_count': len(records), 'eligible_count': len(valid),
            'excluded_count': len(excluded),
            'reason_counts': dict(Counter(reason for entry in excluded for reason in entry['reasons']))}


def finalize_evaluation(record):
    """Keep fetched prices as evidence but never compute returns for a bad bar."""
    errors = price_errors(record)
    if errors:
        record.update(status='invalid', validation_errors=errors)
        for field in RETURN_FIELDS:
            record[field] = None
    else:
        record['status'] = 'evaluated'
        for field, price in RETURN_FIELDS.items():
            record[field] = round((record[price] / record['baseline_close'] - 1) * 100, 2)
        errors = evaluation_errors(record)
        if errors:
            record.update(status='invalid', validation_errors=errors)
            for field in RETURN_FIELDS:
                record[field] = None
    return record

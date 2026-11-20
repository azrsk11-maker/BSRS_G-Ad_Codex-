"""Optional whitelist of already-executed module timings; no runner or cache."""
import math
import re

SCHEMA='bsre-keyword-module-timings-v1'


def withheld():
    return {'schema':SCHEMA,'status':'INCOMPLETE_OR_INVALID','release_authorized':False}


def project(report):
    """Publish every complete module's duration/counters, or no module data.

    This diagnostic never changes execution acceptance. Bodies, case IDs,
    stdout/stderr, paths and unknown fields are never copied into the output.
    """
    try:
        summary=report['summary'];rows=report['modules']
        fields=('discovered_modules','completed_modules','discovered','started','finished','skipped')
        if (type(rows) is not list or not 1<=len(rows)<=256 or
            any(type(summary[k]) is not int or summary[k]<0 for k in fields) or
            summary['passed'] is not True or summary['coverage_verified'] is not True or
            summary['timed_out'] is not False or
            not summary['discovered_modules']==summary['completed_modules']==len(rows) or
            not summary['discovered']==summary['started']==summary['finished']>0):
            return withheld()
        output=[];names=set()
        for row in rows:
            name=row['module'];elapsed=row['elapsed_seconds']
            counts=('expected','started','finished','skipped')
            if (type(name) is not str or re.fullmatch(r'test_[A-Za-z0-9_]{1,160}',name) is None or
                name in names or type(elapsed) not in (int,float) or
                not math.isfinite(elapsed) or not 0<=elapsed<=300 or
                type(row['exit']) is not int or row['exit']!=0 or
                any(row[k] is not True for k in ('complete','coverage_verified','passed')) or
                any(type(row[k]) is not int or row[k]<0 for k in counts) or
                not row['expected']==row['started']==row['finished'] or
                row['skipped']>row['finished']):
                return withheld()
            names.add(name)
            output.append({'module':name,'elapsed_seconds':elapsed,
                           'tests':row['finished'],'skipped':row['skipped']})
        if (sum(r['tests'] for r in output)!=summary['finished'] or
            sum(r['skipped'] for r in output)!=summary['skipped']):
            return withheld()
        return {'schema':SCHEMA,'status':'OBSERVED','module_count':len(output),
            'tests':summary['finished'],'skipped':summary['skipped'],
            'modules':sorted(output,key=lambda r:(-r['elapsed_seconds'],r['module'])),
            'release_authorized':False}
    except (KeyError,TypeError,ValueError,OverflowError):
        return withheld()

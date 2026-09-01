from pathlib import Path
import coverage
_cov=None

def pytest_sessionstart(session):
    global _cov
    _cov=coverage.Coverage(branch=True, source=['smart_independent_audit'])
    _cov.erase(); _cov.start()

def pytest_sessionfinish(session, exitstatus):
    if _cov is None: return
    _cov.stop(); _cov.save(); _cov.json_report(outfile='SMART_COVERAGE_P14_MODULE.json')

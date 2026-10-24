# Engineer wrapper: runs model-authored post-hoc audit without registering a false new experiment.
import os,runpy
from pathlib import Path
p=Path(os.environ['MODELING_PROJECT_DIR'])
os.environ['MODELING_EXPERIMENT_DIR']=str(p/'report/analysis/practical-q1-audit')
runpy.run_path(str(p/'src/q1_recompute_exp0029.py'),run_name='__main__')

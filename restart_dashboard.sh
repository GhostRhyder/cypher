ps aux | grep dashboard.py | grep -v grep | awk '{print $2}' | xargs kill -9
ps aux | grep new_dashboard.py | grep -v grep | awk '{print $2}' | xargs kill -9
nohup python3 new_dashboard.py > dashboard.log 2>&1 &

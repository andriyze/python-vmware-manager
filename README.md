
Python script for powering on/off vms and reverting snapshots on a VMware vSpehere host.

Example:
    python vmware.py -x 10.10.1.1 -u username -p password -v virtualmachinename -a revert -s snapshotname
    python vmware.py -x 10.10.1.1 -u username -p password -v virtualmachinename -a poweron
    python vmware.py -x 10.10.1.1 -u username -p password -v virtualmachinename -a poweroff

VMware vSphere Python SDK pyvmomi used here.
Don't forget to "pip install pyvmomi" first.

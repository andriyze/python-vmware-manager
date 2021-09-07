#!/usr/bin/env python


"""
Python script for powering on/off vms and reverting snapshots on a VMware vSpehere host.

Example:
    python vmware.py -x 10.10.1.1 -u username -p password -v virtualmachinename -a revert -s snapshotname
    python vmware.py -x 10.10.1.1 -u username -p password -v virtualmachinename -a poweron
    python vmware.py -x 10.10.1.1 -u username -p password -v virtualmachinename -a poweroff

VMware vSphere Python SDK pyvmomi used here.
Don't forget to "pip install pyvmomi" first.

Use at your own risk.
"""

from __future__ import print_function
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl
import argparse
import atexit
import getpass
import sys
import ssl

__author__ = "andriyze"

def GetArgs():
   """
   Supports the command-line arguments listed below.
   """
   parser = argparse.ArgumentParser(description='Process args for powering on a Virtual Machine')
   parser.add_argument('-x', '--host', required=True, action='store', help='Remote host to connect to')
   parser.add_argument('-o', '--port', type=int, default=443, action='store', help='Port to connect on')
   parser.add_argument('-u', '--user', required=True, action='store', help='User name to use when connecting to host')
   parser.add_argument('-p', '--password', required=False, action='store', help='Password to use when connecting to host')
   parser.add_argument('-v', '--vmname', required=True, action='append', help='Names of the Virtual Machines to power on')
   parser.add_argument('-a', '--action', required=True, action='store', help='What to do: poweron/poweroff/revert')
   parser.add_argument('-s', '--snapshot', required=False, action='store', help='Name of snapshot')

   args = parser.parse_args()
   return args

def WaitForTasks(tasks, si):
   """
   Given the service instance si and tasks, it returns after all the
   tasks are complete
   """

   pc = si.content.propertyCollector

   taskList = [str(task) for task in tasks]

   # Create filter
   objSpecs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                                                            for task in tasks]
   propSpec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                         pathSet=[], all=True)
   filterSpec = vmodl.query.PropertyCollector.FilterSpec()
   filterSpec.objectSet = objSpecs
   filterSpec.propSet = [propSpec]
   filter = pc.CreateFilter(filterSpec, True)

   try:
      version, state = None, None

      # Loop looking for updates till the state moves to a completed state.
      while len(taskList):
         update = pc.WaitForUpdates(version)
         for filterSet in update.filterSet:
            for objSet in filterSet.objectSet:
               task = objSet.obj
               for change in objSet.changeSet:
                  if change.name == 'info':
                     state = change.val.state
                  elif change.name == 'info.state':
                     state = change.val
                  else:
                     continue

                  if not str(task) in taskList:
                     continue

                  if state == vim.TaskInfo.State.success:
                     # Remove task from taskList
                     taskList.remove(str(task))
                  elif state == vim.TaskInfo.State.error:
                     raise task.info.error
         # Move to next version
         version = update.version
   finally:
      if filter:
         filter.Destroy()

def turn_vm_on(vmList, vmnames, si):
   for vm in vmList:
      if vm.name in vmnames:
         if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
            print("Powering on machine!")
            task = vm.PowerOn()
            WaitForTasks([task], si)
            print("Virtual Machine(s) have been powered ON successfully")
         else:
            print("Virtual Machine(s) already ON")

def turn_vm_off(vmList, vmnames, si):
   for vm in vmList:
      if vm.name in vmnames:
         if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
            print("Powering off machine!")
            task = vm.PowerOff()
            WaitForTasks([task], si)
            print("Virtual Machine(s) have been powered OFF successfully")
         else:
            print("Virtual Machine(s) already OFF")

def revert_vm(vmList, vmnames, snapshot_name, si):
   snapshot_found = False
   for vm in vmList:
      if vm.name in vmnames:
         snapshots = vm.snapshot.rootSnapshotList
         for snapshot in snapshots:
            #print(snapshot.name)
            #print (snapshot.childSnapshotList)
            if snapshot_name == snapshot.name:
               snapshot_found = True
               snap_obj = snapshot.snapshot
               print("LEVEL1 Reverting snapshot ", snapshot.name)
               task = [snap_obj.RevertToSnapshot_Task()]
               break
            for subsnapshot in snapshot.childSnapshotList:
               if snapshot_name == subsnapshot.name:
                  snapshot_found = True
                  snap_obj = subsnapshot.snapshot
                  print("LEVEL2 Reverting snapshot ", subsnapshot.name)
                  task = [snap_obj.RevertToSnapshot_Task()]
                  break
               for subsnapshot2 in subsnapshot.childSnapshotList:
                  if snapshot_name == subsnapshot2.name:
                     snapshot_found = True
                     snap_obj = subsnapshot2.snapshot
                     print("LEVEL3 Reverting snapshot ", subsnapshot2.name)
                     task = [snap_obj.RevertToSnapshot_Task()]
                     break


   if snapshot_found:
      WaitForTasks(task, si)
      print("Done reverting")
   else:
      print("Snapshot *" + str(snapshot_name) + "* not found")

# Start program
def main():
   """
   Simple command-line program for powering on virtual machines on a system.
   """

   args = GetArgs()
   if args.password:
      password = args.password
   else:
      password = getpass.getpass(prompt='Enter password for host %s and user %s: ' % (args.host,args.user))

   try:
      vmnames = args.vmname
      if not len(vmnames):
         print("No virtual machine specified for poweron")
         sys.exit()

      si = None
      context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
      context.verify_mode = ssl.CERT_NONE
      try:
         si = SmartConnect(host=args.host,
                           user=args.user,
                           pwd=password,
                           port=int(args.port),
                           sslContext=context)
      except IOError:
         pass
      if not si:
         print("Cannot connect to specified host using specified username and password")
         sys.exit()

      atexit.register(Disconnect, si)

      # Retreive the list of Virtual Machines from the inventory objects
      # under the rootFolder
      content = si.content
      objView = content.viewManager.CreateContainerView(content.rootFolder,
                                                        [vim.VirtualMachine],
                                                        True)
      vmList = objView.view
      objView.Destroy()


      #Check if vm name is present
      found = False
      for vm in vmList:
         if vm.name in vmnames:
            found = True

      if not found:
         print ("VM specified was not found")
         exit()


      # perform action
      if args.action.lower() == "poweron":
         turn_vm_on(vmList, vmnames, si)
      elif args.action.lower() == "poweroff":
         turn_vm_off(vmList, vmnames, si)
      elif args.action.lower() == "revert":
         if args.snapshot == None:
            print ("You forgot to specify snapshot name. Example: -s snapshotname")
            exit()
         snapshot_name = args.snapshot
         revert_vm(vmList, vmnames, snapshot_name, si)
      else:
         print ("wrong action")


   except vmodl.MethodFault as e:
      print("Caught vmodl fault : " + e.msg)
   except Exception as e:
      print("Caught Exception : " + str(e))

# Start program
if __name__ == "__main__":
   main()

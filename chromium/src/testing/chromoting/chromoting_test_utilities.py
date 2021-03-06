# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility script to run tests on the Chromoting bot."""

import glob
import hashlib
import os
from os.path import expanduser
import shutil
import socket
import subprocess

import psutil

PROD_DIR_ID = '#PROD_DIR#'
CRD_ID = 'chrome-remote-desktop'  # Used in a few file/folder names
CHROMOTING_HOST_PATH = './remoting/host/linux/linux_me2me_host.py'
HOST_READY_INDICATOR = 'Host ready to receive connections.'
BROWSER_TEST_ID = 'browser_tests'
HOST_HASH_VALUE = hashlib.md5(socket.gethostname()).hexdigest()
NATIVE_MESSAGING_DIR = 'NativeMessagingHosts'
# On a Swarming bot where these tests are executed, a temp folder is created
# under which the files specified in an .isolate are copied. This temp folder
# has a random name, which we'll store here for use later.
# Note that the test-execution always starts from the testing/chromoting folder
# under the temp folder.
ISOLATE_TEMP_FOLDER = os.path.abspath(os.path.join(os.getcwd(), '../..'))


def RunCommandInSubProcess(command):
  """Creates a subprocess with command-line that is passed in.

  Args:
    command: The text of command to be executed.
  Returns:
    results: stdout contents of executing the command.
  """

  cmd_line = [command]
  try:
    results = subprocess.check_output(cmd_line, stderr=subprocess.STDOUT,
                                      shell=True)
  except subprocess.CalledProcessError, e:
    results = e.output
  finally:
    print results
  return results


def TestMachineCleanup(user_profile_dir):
  """Cleans up test machine so as not to impact other tests.

  Args:
    user_profile_dir: the user-profile folder used by Chromoting tests.
  """
  # Stop the host service.
  RunCommandInSubProcess(CHROMOTING_HOST_PATH + ' --stop')

  # Cleanup any host logs.
  RunCommandInSubProcess('rm /tmp/chrome_remote_desktop_*')

  # Remove the user-profile dir
  if os.path.exists(user_profile_dir):
    shutil.rmtree(user_profile_dir)


def InitialiseTestMachineForLinux(cfg_file):
  """Sets up a Linux machine for connect-to-host chromoting tests.

  Copy over me2me host-config to expected locations.
  By default, the Linux me2me host expects the host-config file to be under
  $HOME/.config/chrome-remote-desktop
  Its name is expected to have a hash that is specific to a machine.

  Args:
    cfg_file: location of test account's host-config file.

  Raises:
    Exception: if host did not start properly.
  """

  # First get home directory on current machine.
  home_dir = expanduser('~')
  default_config_file_location = os.path.join(home_dir, '.config', CRD_ID)
  if os.path.exists(default_config_file_location):
    shutil.rmtree(default_config_file_location)
  os.makedirs(default_config_file_location)

  # Copy over test host-config to expected location, with expected file-name.
  # The file-name should contain a hash-value that is machine-specific.
  default_config_file_name = 'host#%s.json' % HOST_HASH_VALUE
  config_file_src = os.path.join(os.getcwd(), cfg_file)
  shutil.copyfile(
      config_file_src,
      os.path.join(default_config_file_location, default_config_file_name))

  # Make sure chromoting host is running.
  if not RestartMe2MeHost():
    # Host start failed. Don't run any tests.
    raise Exception('Host restart failed.')


def RestartMe2MeHost():
  """Stops and starts the Me2Me host on the test machine.

  Waits to confirm that host is ready to receive connections before returning.

  Returns:
    True: if HOST_READY_INDICATOR is found in stdout, indicating host is ready.
    False: if HOST_READY_INDICATOR not found in stdout.
  """

  # To start the host, we want to be in the temp-folder for this test execution.
  # Store the current folder to return back to it later.
  previous_directory = os.getcwd()
  os.chdir(ISOLATE_TEMP_FOLDER)

  # Stop chromoting host.
  RunCommandInSubProcess(CHROMOTING_HOST_PATH + ' --stop')
  # Start chromoting host.
  results = RunCommandInSubProcess(CHROMOTING_HOST_PATH + ' --start')

  os.chdir(previous_directory)
  # Confirm that the start process completed, and we got:
  # "Host ready to receive connections." in the log.
  if HOST_READY_INDICATOR not in results:
    return False
  return True


def SetupUserProfileDir(me2me_manifest_file, it2me_manifest_file,
                        user_profile_dir):
  """Sets up the Google Chrome user profile directory.

  Delete the previous user profile directory if exists and create a new one.
  This invalidates any state changes by the previous test so each test can start
  with the same environment.

  When a user launches the remoting web-app, the native messaging host process
  is started. For this to work, this function places the me2me and it2me native
  messaging host manifest files in a specific folder under the user-profile dir.

  Args:
    me2me_manifest_file: location of me2me native messaging host manifest file.
    it2me_manifest_file: location of it2me native messaging host manifest file.
    user_profile_dir: Chrome user-profile-directory.
  """
  native_messaging_folder = os.path.join(user_profile_dir, NATIVE_MESSAGING_DIR)

  if os.path.exists(user_profile_dir):
    shutil.rmtree(user_profile_dir)
  os.makedirs(native_messaging_folder)

  manifest_files = [me2me_manifest_file, it2me_manifest_file]
  for manifest_file in manifest_files:
    manifest_file_src = os.path.join(os.getcwd(), manifest_file)
    manifest_file_dest = (
        os.path.join(native_messaging_folder, os.path.basename(manifest_file)))
    shutil.copyfile(manifest_file_src, manifest_file_dest)


def PrintRunningProcesses():
  processes = psutil.get_process_list()
  processes = sorted(processes, key=lambda process: process.name)

  print 'List of running processes:\n'
  for process in processes:
    print process.name


def PrintHostLogContents():
  host_log_contents = ''
  for log_file in sorted(glob.glob('/tmp/chrome_remote_desktop_*')):
    with open(log_file, 'r') as log:
      host_log_contents += '\nHOST LOG %s\n CONTENTS:\n%s' % (
          log_file, log.read())
  print host_log_contents


def TestCaseSetup(args):
  # Stop+start me2me host process.
  if not RestartMe2MeHost():
    # Host restart failed. Don't run any more tests.
    raise Exception('Host restart failed.')

  # Reset the user profile directory to start each test with a clean slate.
  SetupUserProfileDir(args.me2me_manifest_file, args.it2me_manifest_file,
                      args.user_profile_dir)

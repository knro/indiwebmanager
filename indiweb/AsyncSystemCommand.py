import os
import signal
import subprocess
import threading
import logging

class AsyncSystemCommand:
	"""
	A class to run system commands asynchronously.
	"""
	def __init__(self, command):
		"""
		Initializes the AsyncSystemCommand with the command to be executed.

		Args:
			command (str): The command string to execute.
		"""
		self.command = command
		self.process = None
		self.output = None
		self.error = None
		self.finished = False
		self.lock = threading.Lock()

	def _process_output(self, stream, capture):
		"""
		Processes the output from a given stream (stdout or stderr).

		Args:
			stream (file object): The stream to read from.
			capture (bool): Whether to capture the output to self.output.
		"""
		for line in stream:
			line = line.decode('utf-8').strip()
			with self.lock:
				if capture:
					self.output += line + '\n'
				logging.info(line)

	def run(self):
		"""
		Runs the system command asynchronously.

		Outputs:
			None. The output and error are captured internally.
		"""
		self.finished = False
		self.output = ''
		try:
			self.process = subprocess.Popen(
				self.command,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				shell=True,
				preexec_fn=os.setsid
			)
			logging.info(f"PID OF RUNNING CMD IS {os.getpgid(self.process.pid)}")
			stdout_thread = threading.Thread(target=self._process_output, args=(self.process.stdout, False))
			stderr_thread = threading.Thread(target=self._process_output, args=(self.process.stderr, False))

			stdout_thread.start()
			stderr_thread.start()

			self.process.wait()
			stdout_thread.join()
			stderr_thread.join()

		except Exception as e:
			"""
			Handles exceptions that occur during command execution.
			"""
			logging.info(f"RUN ERROR {e}")
			with self.lock:
				self.error = str(e)
				self.finished = True
		finally:
			logging.info(f"RUN of {self.command} IS FINISHED with output {self.output}")
			with self.lock:
				self.finished = True

	def is_running(self):
		"""
		Checks if the command is currently running.

		Returns:
			bool: True if the command is running, False otherwise.
		"""
		with self.lock:
			return not self.finished

	def terminate(self):
		"""
		Terminates the running command.

		Raises:
			Exception: If an error occurs during termination.
		"""
		if self.process and not self.finished:
			try:
				os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
			except Exception as e:
				logging.error(f"TERMINATE ERROR {e}")
				raise e
			finally:
				with self.lock:
					self.finished = True

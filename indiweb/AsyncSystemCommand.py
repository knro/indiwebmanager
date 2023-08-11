import os
import signal
import subprocess
import threading
import logging

class AsyncSystemCommand:
	def __init__(self, command):
		self.command = command
		self.process = None
		self.output = None
		self.error = None
		self.finished = False
		self.lock = threading.Lock()

	def _process_output(self, stream, capture):
		for line in stream:
			line = line.decode('utf-8').strip()
			with self.lock:
				if capture:
					self.output += line + '\n'
				logging.info(line)

	def run(self):
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
			logging.info(f"RUN ERROR {e}")
			with self.lock:
				self.error = str(e)
				self.finished = True
		finally:
			logging.info(f"RUN of {self.command} IS FINISHED with output {self.output}")
			with self.lock:
				self.finished = True

	def is_running(self):
		with self.lock:
			return not self.finished

	def terminate(self):
		if self.process and not self.finished:
			os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
			with self.lock:
				self.finished = True

# tape_operations_backup.py
import threading
import os
import subprocess
import typer
import time
import signal

class TapeBackup:
    def __init__(self, device_path, block_size, max_concurrent_tars, temp_dir_root):
        self.device_path = device_path
        self.block_size = block_size
        self.max_concurrent_tars = max_concurrent_tars
        self.temp_dir_root = temp_dir_root
        self.all_tars_generated = False
        self.tars_to_be_generated = []
        self.tars_generating = set()
        self.tars_generated = []
        self.tars_to_write = []
        self.generating_lock = threading.Lock()
        self.generated_lock = threading.Lock()
        self.to_write_lock = threading.Lock()
        self.running = True
        self.semaphore = threading.Semaphore(max_concurrent_tars)

    def generate_tar_file(self, directory, index):
        with self.semaphore:
            if not self.running:
                return

            dir_name = os.path.basename(directory)
            temp_tar_path = os.path.join(self.temp_dir_root, f"{dir_name}.tar")
            self.tars_generating.add(temp_tar_path)

            tar_command = ["tar", "-cvf", temp_tar_path, "-b", str(self.block_size), directory]
            subprocess.run(tar_command)

            with self.generating_lock:
                self.tars_generating.remove(temp_tar_path)
            with self.generated_lock:
                self.tars_generated.append((index, temp_tar_path))

            self.check_and_move_to_write()

            if self.is_last_tar_file():
                self.all_tars_generated = True

    def is_last_tar_file(self):
        return len(self.tars_to_be_generated) == 1

    def write_tar_files_to_tape(self):
        while self.tars_to_write or (self.running and not self.all_tars_generated):
            with self.to_write_lock:
                if not self.tars_to_write:
                    continue
                tar_to_write = self.tars_to_write.pop(0)

            self.write_to_tape(tar_to_write)

    def write_to_tape(self, tar_path):
        dd_log_path = os.path.join(self.temp_dir_root, "dd_output.log")
        with open(dd_log_path, 'a') as dd_log:
            dd_log.write(f"\nWriting {tar_path} to tape...\n")
            dd_log.flush()
            dd_command = ["dd", "if={}".format(tar_path), "of={}".format(self.device_path), "bs={}".format(self.block_size), "status=progress"]
            subprocess.run(dd_command, stderr=dd_log)

        subprocess.run(['mt', '-f', self.device_path, 'weof', '1'])
        os.remove(tar_path)

    def continuously_check_and_move(self):
        while not self.all_tars_generated or self.tars_generated:
            self.check_and_move_to_write()
            time.sleep(1)

    def check_and_move_to_write(self):
        with self.generated_lock, self.to_write_lock:
            if self.tars_to_be_generated:
                expected_index, expected_tar = self.tars_to_be_generated[0]
                for generated_index, generated_tar in self.tars_generated:
                    if generated_index == expected_index:
                        self.tars_to_write.append(generated_tar)
                        self.tars_generated.remove((generated_index, generated_tar))
                        self.tars_to_be_generated.pop(0)
                        break

    def backup_directories(self, directories):
        self.tars_to_be_generated = [(index, os.path.join(self.temp_dir_root, f"{os.path.basename(dir)}.tar")) for index, dir in enumerate(directories)]

        tar_threads = [threading.Thread(target=self.generate_tar_file, args=(directory, index)) for index, directory in enumerate(directories)]
        for thread in tar_threads:
            thread.start()

        check_thread = threading.Thread(target=self.continuously_check_and_move)
        check_thread.start()

        dd_thread = threading.Thread(target=self.write_tar_files_to_tape)
        dd_thread.start()

        for thread in tar_threads:
            thread.join()

        self.all_tars_generated = True
        check_thread.join()
        dd_thread.join()

        self.cleanup_temp_files()

    def cleanup_temp_files(self):
        for tar_path in self.tars_generating.union(set(self.tars_generated), set(self.tars_to_write)):
            if os.path.exists(tar_path):
                os.remove(tar_path)

    def exit_handler(self, signum, frame):
        self.running = False
        self.cleanup_temp_files()
        typer.echo("Exiting gracefully...")

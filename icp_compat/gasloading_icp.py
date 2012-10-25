#This program is modified from Brian's pyicp5.py.
#It customizes an icp window for a gas-loading experiment.
#It communicates with the gas-cart laptop and let it execute a gas-loading command
#For standard icp commands, it just passes the commands to the actual icp process.
#Author: Wei Zhou (x8169), Feb 2012

from pyicp import Overlord
import sys

class GasLoadingOverlord(Overlord):
    def __init__(self, prompt_strs = ['% ', ')', '):'], python_esc_str = '@', gasloading_str='#'):
        Overlord.__init__(self, prompt_strs=prompt_strs, python_esc_str=python_esc_str)
        self.gasloading_str = gasloading_str
        self.gasloading_server = xmlrpclib.ServerProxy('http://129.6.122.133:8000')
        sys.stdout.write('Enter a gas-loading command by prefixing with # symbol, e.g.:\n % #loadgas#5.6#2\n    (5.6 mmol gas will be loaded to the sample line using gas port 2)\nEnter a series of commands seperated by ; symbol to run a sequence, e.g.:\n % st=4;rt1;st=120;hold=20;#loadgas#3.1#2;st=4;hold=50;rt2\n')
    
    def do_icp_cmd(self, cmd):
        self.ready = False
        self.icp_command_count += 1
        if cmd.startswith(self.python_esc_str):
            self.do_python_cmd(cmd[1:])
        elif cmd.startswith(self.gasloading_str):
            self.do_gasloading_cmd(cmd[1:])
        else:
            if self.alive:
                sys.stdout.write(cmd + ':')
                self.icp_write.write(cmd + self.newline_str)
                self.icp_write.flush()
    
    def do_gasloading_cmd(self, cmd):
        try:
            # print cmd.split("#")[0]
            if cmd.split("#")[0]=="loadgas":
                gasamount=float(cmd.split("#")[1])
                gasport=cmd.split("#")[2]
                self.gasloading_server.remote_load_gas(gasamount, gasport)
            elif cmd.split("#")[0]=="pumpmanifold":
                self.gasloading_server.remote_pump_manifold()
            elif cmd.split("#")[0]=="pumpsample":
                self.gasloading_server.remote_pump_sample()
        except:
            pass
        sys.stdout.write(self.prompt_str)
        sys.stdout.flush()
        self.ready = True
        return

if __name__ == '__main__':
    overlord = GasLoadingOverlord("% ")
    icp = overlord.do_icp_cmd
    rpsf = overlord.run_py_seq_file
    overlord.start()
    overlord.join()

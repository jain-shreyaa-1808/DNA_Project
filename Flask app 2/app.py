from flask import Flask, render_template, request, redirect, url_for # type: ignore
from radkit_client.sync import sso_login, create_context
import webbrowser
import time
import datetime
import os
import subprocess
import requests
import zipfile
import io
import re

context = create_context()

def is_git_installed():
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError:
        # The git command is not found or returned an error
        return False
    except FileNotFoundError:
        # The git command is not installed
        return False

# Function to clone a repository with Git
def clone_with_git(repo_url, local_path):
    try:
        subprocess.run(["git", "clone", repo_url, local_path], check=True)
        print(f"Repository cloned to {local_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone repository: {e}")

# Function to download and extract a repository ZIP file
def download_repo_zip(repo_zip_url, extract_path):
    response = requests.get(repo_zip_url)
    print(response)
    if response.status_code == 200:
        zip_file = zipfile.ZipFile(io.BytesIO(response.content))
        zip_file.extractall(extract_path)
        zip_file.close()
        print(f"Repository has been downloaded and extracted to: {extract_path}")
    else:
        print("Failed to download the repository")


app = Flask(__name__)

client = ''
devices = []
HOST = '127.0.0.1'
PORT = 5001

@app.route('/', methods=['GET', 'POST'])
def login():
    global client
    if request.method == 'POST':
        email = request.form['email']
        try:
            client = sso_login(email)
        except Exception as e:
            return render_template('login.html', message=e)
        if client:
            return redirect(url_for('service'))
        else:
            return render_template('login.html', message='Login failed. Please try again.')
    return render_template('login.html')

@app.route('/service', methods=['GET', 'POST'])
def service():
    global devices,service1
    if request.method == 'POST':
        serviceid = request.form['serviceid']
        try:
            service1 = client.service(serviceid).wait()
        except Exception as e:
            return render_template('service.html', message=e)
        devices = list(service1.inventory.filter('device_type', 'CISCO_DNA_CENTER'))
        if service1:
            return render_template('service.html', devices=devices)
        else:
            return render_template('service.html', message='Service creation failed. Please try again.')
    return render_template('service.html')

@app.route('/process_device', methods=['POST'])
def process_device():
    global service1,cmd1,ses,dnac
    selected_device = request.form['device']
    dnac = service1.inventory[selected_device]
    ses = dnac.terminal().wait()
    cmd1 = ses.exec("_shell")
    print('Selected Device:', selected_device)
    return redirect(url_for('aberto_verify'))

@app.route('/aberto_verify', methods=['GET', 'POST'])
def aberto_verify():
    global ses,cmd1
    if request.method == 'POST':
        token = request.form['token']
        cmd = ses.exec("_shell -v " + token)
        print(cmd)
        if cmd:
            return redirect(url_for('home'))
        else:
            return render_template('aberto_verify.html', message='Verification failed. Please try again.')
    challenge_data = cmd1.split('\n')[3]
    cmd=''
    if challenge_data=="Proceed to generate a challenge? [y/n] :":
        ses.exec('y').wait()
        cmd=ses.exec('10080').wait()
        challenge_data = cmd.split('\n')[2]
    return render_template('aberto_verify.html', challenge_data=challenge_data)

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/checkfile_dna_ise')
def checkfile_dna_ise():
    global ses
    cmd1=ses.exec("[ -e \"/home/maglev/.magshell/dnac_ise_integration_checker_script.sh\" ] && echo \"Path exists\" || echo \"Path does not exist\"")
    message=cmd1.split("\n")[1]
    return render_template('DNAC_ISE.html',message=message)

@app.route('/checkfile_dna')
def checkfile_cna():
    global ses
    cmd1=ses.exec("[ -e \"/home/maglev/.magshell/DNA_Analyzer_Code-main2/dna_analyzer/DNA_Analyzer.py\" ] && echo \"Path exists\" || echo \"Path does not exist\"")
    message=cmd1.split("\n")[1]
    return render_template('index.html',message=message)

@app.route('/DNAC_ISE',methods=['GET','POST'])
def DNAC_ISE():
    global ses
    if request.method=='POST':
        ISE_IP = request.form['fileInput']
        ISE_IP=ISE_IP.strip()
        ses.exec('cd /home/maglev/.magshell')
        pat= r'\bdnac[\w_-]*\.tar\.gz\b'
        res=ses.exec('ls').split('\n')
        res=str(res)
        data_files=re.findall(pat,res)
        
        for file in data_files:
            ses.exec('rm '+file)
            print(file)
        cmd_list=[
            'bash dnac_ise_integration_checker_script.sh '+ISE_IP ,
            'cd /data/tmp'
        ]

        print("\n\n Executing commands..")
        folder_path = os.path.expanduser("~/Documents/DNAC_logs")

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        #LOCAL_PATH = "DNAC_ISE_INTEGRATION"
        for i in cmd_list:
            print(cmd_list.index(i)+1,'/',len(cmd_list),'...\n')
            print(ses.exec(i))

        res=ses.exec('ls').split('\n')[-2]
        # ls_list=res.split()
        # print(ls_list)
        data_files=re.findall(pat,res)
        for file in data_files:
            ses.exec('mv '+file+ ' /home/maglev/.magshell')
            print(file)

        ses.exec('cd /home/maglev/.magshell')
        res=ses.exec('ls').split(' ')[1:-1]
        res_str=' '.join([str(el) for el in res])
        pat= r'\bdnac[\w_-]*\.tar\.gz\b'
        mag_files=re.findall(pat,res_str)
        mag_files.sort()
        lst=[]
        for file in mag_files:
            LOCAL_PATH=os.path.join(folder_path, file)
            print("Downloading to "+LOCAL_PATH)
            print("\n\n Downloading the tar to local system..\n")
            ses1=dnac.sftp_download_to_file(remote_path=file,local_path=LOCAL_PATH).wait()
            ses1.show_progress()
            lst.append("The log file has been stored in "+str(LOCAL_PATH)+" "+str(ses1.result.status)+"\n")
        print(lst)
        return render_template('DNAC_ISE.html',transfer_status=lst,message='Path exists')
        
    return render_template('DNAC_ISE.html')

@app.route('/SDA_digger')
def SDA_digger():
    return render_template('SDA_digger.html')

@app.route('/AboutSDA')
def AboutSDA():
    return render_template('about_SDA.html')
@app.route('/AboutDNA')
def AboutDNA():
    return render_template('about_DNA.html')
@app.route('/AboutISE')
def AboutISE():
    return render_template('about_ISE.html')

@app.route('/final_selection', methods=['POST'])
def final_selection():
    global ses,cmd
    cmd=ses.exec('cd /home/maglev/.magshell/DNA_Analyzer_Code-main2/dna_analyzer')
    print(cmd)
    chosen_options = request.json
    #print(chosen_options)
    str1="python DNA_Analyzer.py "+" ".join(chosen_options)
    print(str1)
    cmd=ses.exec(str1)
    print(cmd)
    return redirect(url_for('result'))

@app.route('/transfer_files', methods=['GET','POST'])
def transfer_files():
    if request.method=='POST':
        file = request.form['fileInput']
        file_path = file.strip()
        print('File path:', file_path)
        sender=dnac.sftp_upload_from_file(remote_path="/",local_path=file_path)
        while   (str(sender.result.status) != "FileTransferStatus.TRANSFER_DONE") and (sender.result.status != "FileTransferStatus.FAILURE"):
            print(str(sender.result.status))
            print(str(sender.result.status) != "FileTransferStatus.TRANSFER_DONE")
            time.sleep(1)
        print(sender.result.status)
        if '.zip' in file_path:
            print(ses.exec('cd /home/maglev/.magshell'))
            print(ses.exec('python unzip.py'))
        return render_template('transfer.html',message=sender.result.status)
    return render_template('transfer.html')

@app.route('/transfer_git',methods=['GET','POST'])
def transfer_git():
    if request.method=='POST':
        file =request.form['fileInputGit']
        GITHUB_REPO_URL=file.strip()
        REPO_ZIP_URL = GITHUB_REPO_URL[0:-4]+"/archive/refs/heads/main.zip"
        LOCAL_PATH = "DNAC_ISE_INTEGRATION"
        FILE_NAME = "dnac_ise_integration_checker_script.sh"
        # print('File path:', file_path)
        if is_git_installed():
            # Git is installed, use it to clone the repository
            clone_with_git(GITHUB_REPO_URL, LOCAL_PATH)
            local_script_path = os.path.join(LOCAL_PATH, FILE_NAME)
        else:
            # Git is not installed, download the repository as a ZIP file
            download_repo_zip(REPO_ZIP_URL, LOCAL_PATH)
            local_script_path = os.path.join(LOCAL_PATH, "DNAC_ISE_INTEGRATION-main", FILE_NAME)

        # Check if the script file exists at the constructed path
        if os.path.exists(local_script_path):
            print(f"File found at {local_script_path}")
            # You can now use 'local_script_path' as the path to your file
        else:
            print(f"File not found at {local_script_path}")
        ######

        sender=dnac.sftp_upload_from_file(remote_path="/",local_path=local_script_path).wait()
        # ses1.show_progress()
        # sender=dnac.sftp_upload_from_file(remote_path="/",local_path=file_path)
        while   (str(sender.result.status) != "FileTransferStatus.TRANSFER_DONE") and (sender.result.status != "FileTransferStatus.FAILURE"):
            print(str(sender.result.status))
            print(str(sender.result.status) != "FileTransferStatus.TRANSFER_DONE")
            time.sleep(1)
        print(sender.result.status)
        return render_template('transfer_git.html',message=sender.result.status)
    return render_template('transfer_git.html')

@app.route('/transfer_git_dna',methods=['GET','POST'])
def transfer_git_dna():
    global ses
    if request.method=='POST':
        file =request.form['fileInputGit']
        GITHUB_REPO_URL=file.strip()
        REPO_ZIP_URL = GITHUB_REPO_URL[0:-4]+"/archive/refs/heads/main.zip"
        LOCAL_PATH = "DNA_ANALYSER"
        FILE_NAME = "DNA_Analyzer_Code-main2.zip"
        # print('File path:', file_path)
        if is_git_installed():
            # Git is installed, use it to clone the repository
            clone_with_git(GITHUB_REPO_URL, LOCAL_PATH)
            local_script_path = os.path.join(LOCAL_PATH, FILE_NAME)
        else:
            # Git is not installed, download the repository as a ZIP file
            download_repo_zip(REPO_ZIP_URL, LOCAL_PATH)
            local_script_path = os.path.join(LOCAL_PATH, "DNA_Analyzer_Code-main2", FILE_NAME)

        # Check if the script file exists at the constructed path
        if os.path.exists(local_script_path):
            print(f"File found at {local_script_path}")
            # You can now use 'local_script_path' as the path to your file
        else:
            print(f"File not found at {local_script_path}")
        ######

        sender=dnac.sftp_upload_from_file(remote_path="/",local_path=local_script_path).wait()
        # ses1.show_progress()
        # sender=dnac.sftp_upload_from_file(remote_path="/",local_path=file_path)
        while   (str(sender.result.status) != "FileTransferStatus.TRANSFER_DONE") and (sender.result.status != "FileTransferStatus.FAILURE"):
            print(str(sender.result.status))
            print(str(sender.result.status) != "FileTransferStatus.TRANSFER_DONE")
            time.sleep(1)
        print(sender.result.status)

        local_send_path = os.path.join(LOCAL_PATH,  "unzip.py")
        sender2=dnac.sftp_upload_from_file(remote_path="/",local_path=local_send_path).wait()
        
        while   (str(sender2.result.status) != "FileTransferStatus.TRANSFER_DONE") and (sender2.result.status != "FileTransferStatus.FAILURE"):
            print(str(sender2.result.status))
            print(str(sender2.result.status) != "FileTransferStatus.TRANSFER_DONE")
            time.sleep(1)
        print(sender2.result.status)
        print(ses.exec('cd /home/maglev/.magshell'))
        print(ses.exec('python unzip.py'))
        #unzip=ses.exec('unzip '+FILE_NAME)
        #ses.exec('All')
        # print("Unzipped sucessfully")
        return render_template('transfer_git_dna.html',message=sender.result.status)
    return render_template('transfer_git_dna.html')

@app.route('/result')
def result():
    global cmd
    output = cmd  # Assuming cmd contains the final output

    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"DNA_Analyser_logs_{current_datetime}.log"

    folder_path = os.path.expanduser("~/Documents/DNAC_logs")

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    file_path = os.path.join(folder_path, file_name)
    with open(file_path, 'w') as file:
        file.write(output)

    if os.path.exists(file_path):
        msg="The output logfile has been saved in :"+file_path
    else:
        msg="The output logfile creation in the local system failed"

    return render_template('result.html', output=output,msg=msg)



if __name__ == '__main__':
    webbrowser.open(f'http://{HOST}:{PORT}')
    app.run(debug=True, host=HOST, port=PORT)

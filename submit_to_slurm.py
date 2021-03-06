import sys
from subprocess import run
from pathlib import Path
import json
import re
from parameters import parameters, parameters_deep, parameters_vanilla
import datetime
from results.database import add_to_database, clean_database

clean_database()

#  profile = False
profile = True
if len(sys.argv) < 2:
    print("Please specifiy the name of the .py file to execute.")
    sys.exit()


file_name = sys.argv[1]
if file_name[-3:] == '.py':
    file_name = file_name[:-3]

print(f'submit_to_slurm.py will submit the file {file_name}.py')

if file_name == 'main_qlearning':
    parameters.update(parameters_vanilla)
    output_folder_name = 'q_learning'
    job_name = 'QLearning'
elif file_name == 'main_DQL':
    parameters.update(parameters_deep)
    output_folder_name = 'deep_q_learning'
    job_name = 'DQL'
else:
    raise ValueError('Wrong file name.')


if len(sys.argv) < 3:
    n_arrays = 1
else:
    n_arrays = int(sys.argv[2])


#  output = Path('.') / 'output'
output = Path('/data3/bolensadrien/output')
run(['mkdir', '-p', output])


def largest_existing_job_index():
    dirs_starting_with_a_number = [
        d.name for d in output.iterdir() if d.is_dir() and
        d.name[:1].isdigit()
    ]
    if not dirs_starting_with_a_number:
        return None
    return max(int(re.search(r"\d+", dir_str).group()) for dir_str in
               dirs_starting_with_a_number)


def submit_to_slurm(params):
    job_index = (largest_existing_job_index() or 0) + 1
    output_folder_name_indexed = f'{job_index}_' + output_folder_name

    job_path = output / output_folder_name_indexed
    job_path = job_path.absolute()
    run(['mkdir', '-p', job_path])

    info_dic = {
        'n_submitted_tasks': n_arrays,
        'parameters': params
    }

    with (job_path / "info.json").open('w') as f:
        json.dump(info_dic, f, indent=2)
    print("info.json written.")

    options = {
        "array": f"1-{n_arrays}",
        "partition": "long",
        #  "partition": "medium",
        #  "partition": "short",
        "job-name": f'{job_index}_{job_name}',
        "time": "5-00:00:00",
        #  "time": "48:00:00",
        #  "time": "0:30:00",
        #  "mail-type": "END",
        #  "mem-per-cpu": "50000",
        "mem-per-cpu": "20000",
        #  "mem-per-cpu": "5000",
        #  "mem-per-cpu": "500",
        "o": job_path / "slurm-%a.out"
    }

    options_str = ""
    for name, value in options.items():
        if len(name) == 1:
            options_str += f"#SBATCH -{name} {value}\n"
        else:
            options_str += f"#SBATCH --{name}={value}\n"

    python_files = ['models', 'environments', 'systems']
    if file_name == 'main_DQL':
        python_files += ['deep_q_learning', 'main_DQL']
    elif file_name == 'main_qlearning':
        python_files += ['q_learning', 'main_qlearning']

    python_str = ""

    # save current state of python modules :
    for name in python_files:
        run(['cp', Path(__file__).absolute().parent / f'{name}.py', job_path])
        python_str += f"cp {job_path}/{name}.py $WORK_DIR\n"

    if profile:
        run_command = (f'python -m cProfile -o file.prof {file_name}.py '
                       f'$SLURM_ARRAY_TASK_ID')
        copy_prof_files = "cp ./*.prof $OUTPUT_DIR\n"
    else:
        run_command = f"python {file_name}.py $SLURM_ARRAY_TASK_ID"
        copy_prof_files = ""

    job_script_slurm = (
        "#!/bin/bash\n\n"
        f"{options_str.strip()}\n\n"
        "WORK_DIR=/scratch/$USER/$SLURM_ARRAY_JOB_ID'_'$SLURM_ARRAY_TASK_ID\n"
        "mkdir -p $WORK_DIR\n"
        f"{python_str}\n"
        f"cp {job_path / 'info.json'} $WORK_DIR\n"
        "module purge\n"
        "module load intelpython3.2019.0.047\n"
        "cd $WORK_DIR\n"
        f"{run_command}\n\n"
        f"OUTPUT_DIR={job_path}/array-$SLURM_ARRAY_TASK_ID\n"
        "mkdir -p $OUTPUT_DIR\n"
        f"cp ./results_info.json $OUTPUT_DIR\n"
        "cp ./*.npy $OUTPUT_DIR\n"
        "cp ./*.csv $OUTPUT_DIR\n"
        "cp ./*.txt $OUTPUT_DIR\n"
        f"{copy_prof_files}"
        "cd\n"
        "rm -rf $WORK_DIR\n"
        "unset WORK_DIR\n"
        "unset OUTPUT_DIR\n"
        "exit 0"
        )

    with (job_path / "job_script_slurm.sh").open('w') as f:
            f.write(job_script_slurm)

    run([
        "sbatch",
        f"{job_path}/job_script_slurm.sh"
    ])

    alg = None
    if file_name == 'main_qlearning':
        alg = 'q_learning'
        if params['is_rerun']:
            alg = 'q_learning_rerun'
    #  if re.match(r'\d*_deep_q_learning', output_folder_name_indexed):
    if file_name == 'main_DQL':
        alg = 'deep_q_learning'
        if params['subclass'] == 'WithReplayMemory':
            alg = 'DQN_ReplayMemory'
    add_to_database({
        'name': output_folder_name_indexed,
        'status': 'running',
        'n_completed_tasks': 0,
        'n_submitted_tasks': n_arrays,
        'submission_date': str(datetime.datetime.now()),
        'algorithm': alg
    })


if __name__ == '__main__':
    #  import math
    #  for t in [1.0, 1.25, 1.5, 1.75, 2.0, 5.0, 10.0, 100.0]:
    #      parameters['time_segment'] = t
    #      submit_to_slurm(parameters)
    #  for n in range(5, 30, 4):
    #      parameters['n_initial_actions'] = n
    #      submit_to_slurm(parameters)
    #  for n in range(5, 150, 20):
    #      parameters['capacity'] = n
    #      parameters['sampling_size'] = n
    #      submit_to_slurm(parameters)
    #  parameters['n_sites'] = 11
    #  parameters['time_segment'] = 1.0
    #  submit_to_slurm(parameters)
    #  parameters['time_segment'] = 100.0
    #  parameters['range_all'] = 1.0
    #  parameters['range_one'] = math.pi
    #  submit_to_slurm(parameters)

    parameters['range_all'] = 0.5
    parameters['range_one'] = 1.0
    submit_to_slurm(parameters)

    parameters['range_all'] = 0.1
    parameters['range_one'] = 0.5
    submit_to_slurm(parameters)

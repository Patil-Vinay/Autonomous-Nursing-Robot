from glob import glob

from setuptools import setup

package_name = 'scobo_tasks'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Vinay Patil',
    maintainer_email='77240925+Patil-Vinay@users.noreply.github.com',
    description='Ward plan, scheduler and bed visits for the SCOBO nursing robot',
    license='MIT',
    entry_points={
        'console_scripts': [
            'task_manager = scobo_tasks.task_manager:main',
            'send_plan = scobo_tasks.send_plan:main',
        ],
    },
)

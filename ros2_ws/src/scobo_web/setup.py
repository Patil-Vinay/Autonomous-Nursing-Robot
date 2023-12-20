from glob import glob

from setuptools import setup

package_name = 'scobo_web'

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
    description='Link between the SCOBO nursing robot and the ward website',
    license='MIT',
    entry_points={
        'console_scripts': [
            'web_link = scobo_web.web_link:main',
            'robot_pose = scobo_web.robot_pose:main',
        ],
    },
)

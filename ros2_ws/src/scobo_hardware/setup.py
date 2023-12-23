from glob import glob

from setuptools import setup

package_name = 'scobo_hardware'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Vinay Patil',
    maintainer_email='patilb.vinay@gmail.com',
    description='Drivers for the SCOBO nursing robot: the Mega 2560 link, MLX90640 and lidar scan',
    license='MIT',
    entry_points={
        'console_scripts': [
            'mega_bridge = scobo_hardware.mega_bridge:main',
            'mlx90640 = scobo_hardware.mlx90640:main',
            'scan_crop = scobo_hardware.scan_crop:main',
        ],
    },
)

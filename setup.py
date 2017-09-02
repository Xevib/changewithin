from setuptools import setup, find_packages
with open('requirements.txt') as f:
    data = f.read()
requirements = data.split()

setup(
    name='changewithin',
    version='0.1.0',
    packages=find_packages(),
    url='https://github.com/Xevib/changeswihtin',
    license='MIT',
    author='Xavier Barnada',
    author_email='xbarnada@gmail.com',
    description='Tool to generate reports',
    install_requires=requirements,
    include_package_data=True,
    entry_points='''
        [console_scripts]
        changewithin=changewithin.cli:cli_generate_report
    ''',
    package_data={
        'changewithin': [
            "changewithin/templates/text_template.txt",
            "changewithin/templates/html_template.html"
        ]
    }
)
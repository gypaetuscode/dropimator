#!/bin/bash

#? Cleanup old files
cd /home/dev/projects/power_store;
rm -r *.csv;

#? Get updated CSV File
cd /home/dev/projects/power_store/get_csv;
rm -r *.csv;
source venv/bin/activate;
python3 main.py;

if [ -z "$(find . -maxdepth 1 -type f -name '*.csv')" ]; then
 echo 'No CSV File'
 exit 1
fi

mv *.csv /home/dev/projects/power_store;

deactivate;
cd /home/dev/projects/power_store;

source venv/bin/activate;
python3 main.py;

deactivate;
cd /home/dev/projects/power_store/sync;
php index.php;
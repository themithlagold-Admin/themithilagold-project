#!/bin/bash

echo "BUILD START"

# Install requirements
python3.12 -m pip install -r requirements.txt

# Collect static files
python3.12 manage.py collectstatic --noinput --clear

# NOTE: migrate is intentionally NOT run here.
# Vercel's static-build phase has no DATABASE_URL, so migrations
# are executed in wsgi.py at Lambda cold-start instead.



echo "BUILD END"

#!/usr/bin/env bash
#

# create pyenv environments for each minor version of python
# supported by this project
#
# this script uses terms from Semantic Versioning https://semver.org/
# version numbers are: major.minor.patch
#
# this script will delete and recreate existing virtualenvs named
# cmd2-3.7, etc. It will also create a .python-version
#
# Prerequisites:
#   - *nix-ish environment like macOS or Linux
#   - pyenv installed
#   - pyenv-virtualenv installed
#   - readline and openssl libraries installed so pyenv can
#     build pythons
#

# Make a array of the python minor versions we want to install.
# Order matters in this list, because it's the order that the
# virtualenvs will be added to '.python-version'. Feel free to modify
# this list, but note that this script intentionally won't install
# dev, rc, or beta python releases
declare -a pythons=("3.7" "3.6" "3.8" "3.9")

# function to find the latest patch of a minor version of python
function find_latest_version {
    pyenv install -l | \
    sed -En -e "s/^ *//g" -e "/(dev|b|rc)/d" -e "/^$1/p" | \
    tail -1
}

# empty out '.python-version'
> .python-version

# loop through the pythons
for minor_version in "${pythons[@]}"
do
    patch_version=$( find_latest_version "$minor_version" )
    # use pyenv to install the latest versions of python
    # if it's already installed don't install it again
    pyenv install -s "$patch_version"

    envname="cmd2-$minor_version"
    # remove the associated virtualenv
    pyenv uninstall -f "$envname"
    # create a new virtualenv
    pyenv virtualenv -p "python$minor_version" "$patch_version" "$envname"
    # append the virtualenv to .python-version
    echo "$envname" >> .python-version
done

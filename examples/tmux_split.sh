#!/usr/bin/env zsh

# This script launches two applications using byobu in different tabs.
# The user is required to enter the name of at least the first application.
# If the second isn't provided, then the user's default shell is launched for this.
#
# byobu must be installed for this script to work and you can install it using your
# operating system package manager. For info on how to use Byobu, see: https://www.byobu.org/
#
# To shift focus between tabs in byobu, just hit F3.

# Function to print in red
print_red() {
    echo -e "\e[31m$*\e[0m"
}

if [ $# -eq 0 ];
  then
    print_red  "No arguments supplied and this script requires at least one"
    exit 1
fi

FIRST_COMMAND=$1

if [ $# -eq 1 ]
  then
    SECOND_COMMAND=$SHELL
  else
    SECOND_COMMAND=$2
fi

tmux new-session -s "tmux split pane demo" "$FIRST_COMMAND ; read" \; \
  split-window "$SECOND_COMMAND ; read" \; \
  select-layout even-vertical

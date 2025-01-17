#!/usr/bin/env zsh

# This script launches two applications using tmux in different windows/tabs.
# The user is required to enter the name of at least the first application.
# If the second isn't provided, then the user's default shell is launched for this.
# You must have tmux installed and that can be done using your operating system's package manager.
#
# See the tmux Wiki for info on how to use it: https://github.com/tmux/tmux/wiki.
# To shift focus between different windows in tmux use Ctrl-b followed by l (lowercase "L").
#
# NOTE: If you have byobu installed, it is a wrapper around tmux and will likely run instead of tmux.
# For info on how to use Byobu, see: https://www.byobu.org/
# To shift focus between windows/tabs in byobu, simply hit F3.

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

tmux new-session -s "tmux window demo" -n "$FIRST_COMMAND" "$FIRST_COMMAND ;read" \; \
  new-window -n "$SECOND_COMMAND" "$SECOND_COMMAND ; read" \; previous-window

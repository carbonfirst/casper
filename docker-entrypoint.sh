#!/usr/bin/env bash

#set -e -o pipefail
echo "Script executed from: ${PWD}"
echo "$DATA"
echo "Printing all files in current directory"

for file in *
do
    if [ -f "$file" ]
    then
        echo "$file"
    fi
done

if [ $# -eq 0 ]; then
    # run server if there are .zim files
    if compgen -G "$DATA/*.zim" > /dev/null; then
        exec kiwix-serve --port 8080 "$DATA"/*.zim
    else
        echo "NO .zim FILES WERE FOUND!"
        echo "Starting bash!"
        exec "/bin/bash"
    fi
fi

# exec "$@"

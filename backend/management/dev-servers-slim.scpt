-- Apple script to open iterm and run each of the server instances
-- Requires `mewtwo` alias to go to app home directory
-- The list of commands to run in each tab of the terminal window
set cmdList to {"mewtwo && make shell", "mewtwo && make dev-frontend",  "mewtwo && make dev-worker"}
set tabNames to {"Shell", "Frontend",  "Worker"}

-- Initialize iTerm
tell application "iTerm"
    -- Create a new window
    set newWindow to (create window with default profile)
    set firstSession to current session of newWindow

    -- Try setting the bounds
    try
        set bounds of newWindow to {75, 150, 1500, 800}
    on error
        display dialog "Couldn't set window bounds."
    end try

    -- Execute the first command in the first session and set the name
    tell firstSession
        write text (item 1 of cmdList)
        set name to item 1 of tabNames
    end tell

    -- Execute additional commands in new tabs
    repeat with i from 2 to count of cmdList
        -- Create a new tab
        set newTab to (create tab with default profile in newWindow)
        set newSession to current session of newTab

        -- Execute the command in the new tab and set the name
        tell newSession
            write text (item i of cmdList)
            set name to item i of tabNames
        end tell
    end repeat

    -- Focus on the first tab
    tell firstSession
        select
    end tell
end tell

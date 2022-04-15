Hotplug-capable machine plugin for dnaq's HID protocol (linux only)
================================

This used to be an independent plugin for my own attempt at standardizing an HID steno protocol. However, it never got past one user (me), and with the release of dnaq's version I switched over. However, there is one thing that their plugin (due to being built on hidapi) can't really do, and that is automatically detecting a newly connected stenotype. I've been relying on steno for my work the past few days, and it's become clear that this small feature would be a large enough improvement for me to justify digging out this plugin again, fixing it up, and rewriting it for dnaq's protocol.

Based on Ted Morin's Tréal plugin here: https://github.com/morinted/plover-treal/.

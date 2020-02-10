# Key labeling: Problem statement

The goal is to create a simple exchange format that allows the
stenotype device to describe the function of each of its keys to the
host in an automated manner. Ideally, the process should be
system-agnostic and easily extensible, so as to facilitate the
implementation of new systems, even those that were not considered
during this design process.

# The current state: Gemini PR

Currently, all QMK stenotypes have to fit their keylayout into the
scheme provided by Gemini PR. The disadvantage of this is that not
every system is a good fit for the Gemini PR layout. Also, it is
kind of inelegant. The advantage is that any new system that re-uses
the Ireland layout (just with different letters) can easily attach to
the Gemini layout and thus automatically work with all devices that
use Gemini, without having to adapt the device or having to provide a
custom keymap for each one.

# Idea: Device keymaps

One option would be to simply let the device provide a default keymap
(i.e. provide a direct mapping of each key to the intended plover
action, which is a simple string from the system's `KEYS` list), for each
system that the maker of the device wanted to support. The advantage
is that this is very simple and straightforward, and it would still
let the user customize the keymap if they wanted to – the device would
only provide a default. The disadvantage is that this does not work as
well for systems that the device maker did not intend, though note
that this can be alleviated somewhat – if the device provides a keymap
for the Ireland layout, we could still automatically patch
Ireland-based layouts into that automatically. Arguably, this is more
elegant than the Gemini PR solution, since it is not biased in favor
of one system – in fact, there also exist remaps for the palantype
layout (percidae's German palantype) which could take advantage of
such a general system. However, it comes at the cost of increased
implementation complexity.

# Idea: Finger labeling

To remain system-agnostic, we could instead label each key based on
which finger is used to press it, and where it falls within the range
of that finger. If multiple keys are connected together, or a single
key can be used by multiple fingers, this could also be indicated.

For all fingers except for the thumbs, we are assuming that the keys
are generally arranged in vertical columns. We then number the keys
for a particular finger by starting in its "center" column, so like
the one that is easiest to reach, going from top to bottom. If there
are other columns, we could go through them in ascending order of how
hard they are to reach, maybe using some kind of marker to indicate
when we enter a new column. Perhaps we should also indicate whether
the additional columns are left or right of the center one?

The thumbs are a bit more difficult, since they're very
flexible. Intuitively, I would say that here we should go by rows
instead of columns, since horizontal movement is probably still easier
and thus more commonly used across layouts.

I think that the hard part for this system is defining the
constraints well, so that they are reasonably expressive yet not
overly complicated. It is necessarily going to need some assumptions
about how human steno systems place keys, and we'll have to hope that
no one comes up with a system that does not fit into that. (Note, for
example, our initial assumption that each key can be associated with a
certain finger – though I guess you can alleviate this with the
combination marker described above.)

However, as far as those constraints are working, this is probably the
most flexible system. When implemented well, devices and system
plugins could be mutually ignorant of each other, since the layouts
can just be matched automatically. (And we can still allow for user
modification of this automatic default keymap.) On the other hand,
perhaps this isn't even desirable – perhaps manufacturers *want* to
specify the mappings of their machine to a certain system, so as to
guarantee reliable operation.

# Tentative conclusion

Okay, so, based on writing all of this down, it really feels to me,
right now, as if the device keymap solution is actually quite sensible
– if you include the option for systems to "re-skin" existing layouts:
as various systems do with the ireland layout, as german palantype
does with the palantype layout, or (if you're going to do a galaxy
brain take) as the normal steno system does with the Gemini PR layout
(which would otherwise have too many keys).

In a way, some of the infrastructure is already implemented: Systems
provide default keymaps for certain machine types, and machines can
link themselves into these machine types. The problem with
this, I guess, is that this would not allow the user customize access
to all of the keys of each machine, since the machine is already
translating them into the pre-defined machine model. Perhaps the
solution to this would be to only fall back onto the pre-defined
machine type keymap for initialization of the device-specific keymap,
and after that allow arbitrary customization. Like this:

*device keymap*: maps device buttons to keys of a pre-defined machine
type  
*system keymap*: maps keys of the machine type to actions in the system

On setup, we compose these two keymaps (ie take each button first
through the device keymap, and then through the system keymap) to
obtain the system action corresponding to this button. This then
becomes the default keymap for this (device/system) combination, and
is what will be shown in the configurator.

Yeah I really like this actually... Maybe we'll need a way for the
device to say, okay, no, now I actually want to provide a system
keymap directly. But overallthis seems solid to me, and tick all of
the boxes.
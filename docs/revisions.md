## Latest
- BUG FIX : evaluate class description must be over the class header
- FEATURE : refPlaceholder in reference system
- FEATURE : subprocess' stderr can be handle as stdout (from task to task), so if a subprocess support write to stdout when error was chatched,it can be read out from channel in AKEP 
- BUG FIX : external channel input type
- FEATURE : add analyse modul

## Release AKEP 2.0
- Total rewrite AKEP 1.0
- Moduls add
- New reference system
- New evaluate system
- Logger
- New global error handling
- Config hierarhy (in akep.cfg > akep.local.cfg > exercise exerciseKeys > in command to socketSever)
- New easier schema
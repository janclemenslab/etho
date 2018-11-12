- set scanimage scan dur to inf and savefilename
- arm scanimage grab/loop trigger
- this calls user fun which triggers python script that will send the savefilename
- this will select playlist selected in python (or simple matlab gui for listing and selecting from a set of playlist files?)
- py controls start/nextfile/stop (but still only a single daq file or split on each nextfile trigger - e.g. different hdf5 dataset for each tif file)
- implement trigger - can we treat is as another ao channel? e.g. append trigger pattern to output data? or just record daq into a single file and record next-file trigger with it
£ other things todo:
- record pixel and/or scan clocks

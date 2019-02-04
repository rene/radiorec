# Radiorec

Radiorec it's a simple program to play and record audio streams

## Versions

Original version was implemented using *PyGtk2* and *PyGst  0.10*. This
version is available at **pygtk2** branch. The **master** branch
contains the code ported to work with the newer versions, *PyGtk3* and *PyGst 1.0*.

## How to  Run:

Just execute *radiorec* at source root tree:

```bash
$ ./radiorec
```

**NOTE**: Not all stream servers send information about their music.
          In this case, titles, time duration, genres, etc, will not
          be avaliable. But you can keep record streams, Radiorec will
          use "untitled" as title and "unknown" as the others.
          Beaware just if you record two consecutive streams that not
          send information, because output file name could be the same,
          overwriting record files. 


## Acknowledges

To Tango Icon Library team, because their icons were used to create Radiorec icon.

## Bug report

Please, report them to [rene@renesp.com.br](mailto:rene@renesp.com.br)


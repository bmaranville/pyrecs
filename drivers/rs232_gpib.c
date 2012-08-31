/*
 * Routines to communicate over GPIB via a National Instruments GPIBCT module
 *
 * Author: Nick Maliszewskyj, NIST Center for Neutron Research
 * $Id: rs232_gpib.c,v 1.9 2003/10/07 18:44:38 nickm Exp $
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include "serial.h"
#include "rs232.h"
#include "instrext.h"
#include "trace.h"

#define UNL     0x3F
#define UNT     0x5F
#define GET     0x08
#define MTA(x) (0x40 + x)
#define MLA(x) (0x20 + x)

#define CHUNK  64

extern RS232PARM rs232_cnf[NUMRS232];
extern int debug;

static int gpib_fd=0;
static int gpib_pad=0;
static char outbuf[256];

static int
ibcac(int when) {
  int n;
  /* when = 0 : Take control immediately
     when = 1 : Take control synchronously */
  sprintf(outbuf,"cac %d\r",when);
  if (debug & 1) { TRACE("ibcac: Send ->%s<-\n",outbuf); }
  if ((n = write(gpib_fd,outbuf,strlen(outbuf))) != strlen(outbuf)) 
    return -1;
  return 0;  
}

static int
ibsic() {
  int n;
  sprintf(outbuf,"sic\r");
  if (debug & 1) { TRACE("ibsic: Send ->%s<-\n",outbuf); }
  if ((n = write(gpib_fd,outbuf,strlen(outbuf))) != strlen(outbuf)) 
    return -1;
  return 0;
}

static int
ibcmd(int cmd) {
  int n;
  sprintf(outbuf,"cmd\n%c\r",(char) cmd);
  if (debug & 1) { TRACE("ibcmd: cmd %d\n",cmd); }
  if ((n = write(gpib_fd,outbuf,strlen(outbuf))) != strlen(outbuf)) 
    return -1;
  return 0;
}

static int
ibwrt(int addr, char * buf, int buflen) {
  char * ptr;
  int n;

  memset(outbuf,0,sizeof(outbuf));
  if (((ptr = strchr(buf,'\n')) != NULL) || 
      ((ptr = strchr(buf,'\r')) != NULL)) {
    sprintf(outbuf,"wr #%d %d\n", buflen, addr);
  } else {
    sprintf(outbuf,"wr %d\n", addr);
  }
  n = strlen(outbuf);
  memcpy(outbuf+n, buf, buflen);
  
  /* strcat(outbuf,buf);*/ /* Should probably do memcpy */
  strcat(outbuf,"\r");
  if (debug & 1) { TRACE("ibwrt: Send ->\n%s\n<-\n",outbuf); }
  if ((n = write(gpib_fd,outbuf,strlen(outbuf))) != strlen(outbuf)) 
    return -1;
  return n;
}

static int
ibrd(int addr, int bytes, char * inbuf) {
  int i,n,len, templen;
  char ch;
  char buf[80];
  /* Request bytes from the controller */
  /* Flush */
  serialFlush(gpib_fd);
  sprintf(outbuf,"rd #%d %d\r",bytes-10,addr);
  if (debug & 1) { TRACE("ibrd: Send ->\n%s\n<-\n",outbuf); }  
  if ((n = write(gpib_fd,outbuf,strlen(outbuf))) != strlen(outbuf)) 
    return -1;

  usleep(50);
  /* A simple read should suffice */
  if ((n = read(gpib_fd,inbuf,bytes)) < 0) {
    /* Complain */
    perror("ibrd");
    return n;
  } else {
    if (n > bytes-10) {
      memset(buf,0,sizeof(buf));
      memcpy(buf,(inbuf + bytes - 10),(n + 10 - bytes));
      i = atoi(buf);
      if (debug & 1) { TRACE("ibrd: len ->%d<-\n",i); }
      len = i;
    }

    if (debug & 1) { TRACE("ibrd: Recv ->\n%s\n<-\n",inbuf); }  
  }
  len = n; 

  return len; 
}

/* 
 * Initialize serial port 
 */
void
RS232G_INIT(){
  /* Get port number from FORTRAN side through "instr" common block */
  int portno;
  portno = _CINSTR.term_line;
  if (debug) TRACE("RS232G_INIT: portno = %d device = %s\n",
		    portno,rs232_cnf[portno].dev);
  if (portno < 0) {
    fprintf(stderr,"RS232G_INIT: Can't initialize portno %d\n",portno);
    gpib_fd = -1;
    return;
  }
  if ((gpib_fd = serialOpen(rs232_cnf[portno].dev, 
			    rs232_cnf[portno].baud, 
			    rs232_cnf[portno].bits, 
			    rs232_cnf[portno].parity,
			    0)) < 0) {
    fprintf(stderr,"RS232G_INIT: open() failed!\n");
    exit(2);
  }

  ibsic(); /* Send interface clear */
}

void
RS232G_END(){
  if (gpib_fd > 0) close(gpib_fd);
  gpib_fd = 0;
}


void
GPIBCT_LISTEN(int * addr, int * err) {
  if (debug) printf("GPIBCT_LISTEN MLA(%d)\n",*addr);
  *err = ibcmd(MLA(*addr)); /* Set device to be listener */
  *err = ibcmd(MTA(0));     /* Set controller to be talker */
  gpib_pad = *addr;

}

void
GPIBCT_UNL(int * err) {
  *err = ibcmd(UNL);
  gpib_pad = 0;
}

void
GPIBCT_TALK(int * addr, int * err) {
  if (debug) printf("GPIBCT_TALK MTA(%d)\n",*addr);
  *err = ibcmd(MTA(*addr)); /* Set device to be talker */
  *err = ibcmd(MLA(0));     /* Set controller as listener */
  gpib_pad = *addr;
}

void
GPIBCT_UNT(int * err) {
  *err = ibcmd(UNT);
  gpib_pad =0;
}

/* Send "Group Execute Trigger" */
void
GPIBCT_EXECUTE(int * err) {
  *err = ibcmd(GET);
}

int
GPIBCT_WR(char * string, int * length, int * err) {
  int n;
  *err = 0;
  if (debug) TRACE("GPIBCT_WR: gpib_pad = %d\n",gpib_pad);

  n = ibwrt(gpib_pad, string, *length);
  return n;
}

int
GPIBCT_RD(char * string, int * length, int * err) {
  int n, i, outlen;
  char ch;
  *err = 0;
  n = ibrd(gpib_pad, 80, string);
  for (i=0;i<n;i++) {
    if (!isprint((ch = string[i]))) {
      ch = ' ';
      string[i] = ch;
    }
  }
  *length = n;
  return n;
}

int
GPIBCT_RDBLK(char * string, int * expected, int * length, int * err) {
  int i, n, nchunks, nlastchunk,total;
  char * ptr;
  time_t t1, t2;

  *err = 0;

  /* Request bytes from the controller */
  if (debug) TRACE("GPIBCT_RDBLK: Request %d bytes\n",*expected);
  time(&t1);
  sprintf(outbuf,"rd #%d %d\r",*expected,gpib_pad);
  nchunks = *expected / CHUNK;
  nlastchunk = *expected % CHUNK;

  if ((n = write(gpib_fd,outbuf,strlen(outbuf))) != strlen(outbuf)) {
    *err = -1;
    return -1;
  }

  /* A simple read will *NOT* do here: Split up the reads into smaller
     chunks */

  /* NOTE potential for a deadlock here */
  ptr = string;
  total = 0;
  if (nchunks) {
    for (i=0;i<nchunks;i++) {
      if ((n = read(gpib_fd, ptr, CHUNK)) < 0) {
	//	switch(errno) {
	//	case EAGAIN:
	//	  i--;
	//	  if (debug) TRACE("GPIBCT_RDBLK (EAGAIN)\n");
	//	  continue;
	//default:
	  perror("GPIBCT_RDBLK (chunk):");
	  *err=-1;
	  return -1;
	  //	}
      }
      ptr += n;
      total += n;
    }
  }

  if (nlastchunk) {
    if ((n = read(gpib_fd,ptr,nlastchunk)) < 0) {
      /* Complain */
      perror("GPIBCT_RDBLK (lastchunk):");
      *err=-1;
      return -2;
    } 
    total += n;
  }
  time(&t2);

  if (debug) TRACE("GPIBCT_RDBLK: Read   %d bytes\n",total);
  if (debug) TRACE("GPIBCT_RDBLK: Duration %ld sec\n",(long)(t2-t1));
  *length = total;

  return total;
}


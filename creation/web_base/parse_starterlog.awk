BEGIN {
  year=strftime("%Y");
  starttime=0;
  ended_jobs=0;
  total_used=0;
  goodputZ=0;
  goodputNZ=0;
  badputSignal=0;
  badputOther=0;
  goodjobsZ=0;
  goodjobsNZ=0;
  badjobsSignal=0;
  badjobsOther=0;
}

# year is a 4 digit string or number
# date is month/day
# time is hour:minute:seconds
function convert_date(year,date,time) {
  split(date,datearr,"/");
  split(time,timearr,":");
  timestr=sprintf("%04d %02d %02d %02d %02d %02d",year,datearr[1],datearr[2],timearr[1],timearr[2],timearr[3]);
  return mktime(timestr)
}

function percent(a,b) {
  if (b==0) {
    return 0;
  } else {
    return a*100/b;
  }
}

########################################################################  
/ Communicating with shadow /{
  # 7/17 10:42:20 (pid:26855) Communicating with shadow <131.225.204.208:34839>
  # 
  for (i=1; i<NF; i++) {
    if ($i=="Communicating") {
      changenr=i;
      break;
    }    
  }
  shadow=$(changenr+3);
  shadow=substr(shadow,2,length(shadow)-2)
  #print  $1,$2,"Shadow:",shadow
}
/ Starting .* job with ID: /{
  # 7/17 10:42:21 (pid:26855) Starting a VANILLA universe job with ID: 40.0
  # 
  for (i=1; i<NF; i++) {
    if ($i=="ID:") {
      changenr=i;
      break;
    }    
  }
  jid=$(changenr+1);
  #print  $1,$2,"Jid:",jid
}
/ Create_Process succeeded, /{
  # 7/17 10:42:21 (pid:26855) Create_Process succeeded, pid=26858
  # 
  for (i=1; i<NF; i++) {
    if ($i=="Create_Process") {
      changenr=i;
      break;
    }    
  }
  pidstr=$(changenr+2);
  split(pidstr,pidarr,"=");
  pid=pidarr[2];
  #print  $1,$2,"PID:",pid

  starttime=convert_date(year,$1,$2);
  print $1,$2,"Starting job",jid,"from",shadow
}
/ Process exited, /{
  # 7/17 10:50:31 (pid:26855) Process exited, pid=26858, signal=9
  # 7/17 11:23:04 (pid:23112) Process exited, pid=23114, status=0
  #
  for (i=1; i<NF; i++) {
    if ($i=="Process") {
      changenr=i;
      break;
    }    
  }
  pidstr=$(changenr+2);
  reasonstr=$(changenr+3);

  split(reasonstr,reasonarr,"=");

  ended=convert_date(year,$1,$2);
  if (ended<starttime) { # around new year
    ended=convert_date(year+1,$1,$2);
  }

  if (starttime>0) {
    joblength=ended-starttime;
  } else {
    # protect from incomplete data
    joblength=0;
  }

  ended_jobs++;
  total_used+=joblength;

  print $1,$2,"Terminated job",jid,"from",shadow,reasonarr[1],reasonarr[2],"duration",joblength
  if (reasonarr[1]=="status") {
    if (reasonarr[2]=="0") {
      goodputZ+=joblength;
      goodjobsZ++;
    } else {
      goodputNZ+=joblength;
      goodjobsNZ++;
    }
  } else if (reasonarr[1]=="signal") {
    badputSignal+=joblength;
    badjobsSignal++
  } else {
    badputOther+=joblength;
    babjobsOther++;
  }

  # cleanup, so it is not reused by accident
  jid="";
  shadow="";
  starttime=0;
}

/^===NewFile===/{
  if (starttime>0) {
    print "Termination event for job",jid,"from",shadow,"not found"
  }
  # cleanup, so it is not reused by accident
  jid="";
  shadow="";
  starttime=0;
} 
########################################################################  
END {
  print "=================";
  print "Total jobs",ended_jobs,"utilization",total_used;
  print "Total goodZ jobs",goodjobsZ " (" percent(goodjobsZ,ended_jobs) "%)","utilization",goodputZ " (" percent(goodputZ,total_used) "%)";
  print "Total goodNZ jobs",goodjobsNZ " (" percent(goodjobsNZ,ended_jobs) "%)","utilization",goodputNZ " (" percent(goodputNZ,total_used) "%)";
  print "Total badSignal jobs",badjobsSignal " (" percent(badjobsSignal,ended_jobs) "%)","utilization",badputSignal " (" percent(badputSignal,total_used) "%)";
  print "Total badOther jobs",badjobsOther " (" percent(badjobsOther,ended_jobs) "%)","utilization",badputOther " (" percent(badputOther,total_used) "%)";
}

;test_data_generation.pro
;
; Utility to rotate a 16-bit number to the right by one bit
;
function soh_rotate, number
;
; Input Variables:
;   number    (int): the number to be rotated
;
; Output Variables:
;   number    (int): the number to be rotated
;
; Local Variables:
;   leastbit (long): least significant bit of the number
;
; Called From:
;   ssmis_compute_checksum (ssmis_compute_checksum.pro)
;
; Routines Called:
;  (none)
;

  leastbit = number and 1u
  return, ishft(number, -1) or ishft(leastbit, 15)
end

;
; Compute the checksum of an SSMIS scan.
;
function ssmis_compute_checksum, dataframes, no_reverse=nr
;
; Input Variables:
;   dataframes   (pointer): data frames for which the checksum will be computed
;   nr               (int): if true, don't reverse the 12-bit words
;
; Output Variables:
;   checksums (long array): the resulting checksum value
;
; Local Variables:
;   s         (long array): size of dataframes
;   nframe          (long): upper limit for the loop counter
;   dataframe (long array): input data frames truncated to 16 bits
;   i               (long): loop counter
;
; Called From:
;   soh_read_early (ssmis_readpkt.pro)
;
; Routines Called:
;   soh_rotate     (ssmis_compute_checksum.pro)
;

  s = size(dataframes)
  checksums = uintarr(s[2])
  nframe = s[1] - 3L

;
; Iterate through groups of three 12-bit words (each comprising a single
; 36-bit word).  Skip the calculation if the current 36-bit word is a fill
; word.l
;
  if (keyword_set(nr) eq 0) then begin
    for i = 0L, nframe, 3 do begin
      checksums = soh_rotate((temporary(checksums) + dataframes[i+2,*]))
      checksums = soh_rotate((temporary(checksums) + dataframes[i+1,*]))
      checksums = soh_rotate((temporary(checksums) + dataframes[i,*]))
    endfor
  endif else begin
    for i = 0L, nframe, 3 do begin
      checksums = soh_rotate((temporary(checksums) + dataframes[i,*]))
      checksums = soh_rotate((temporary(checksums) + dataframes[i+1,*]))
      checksums = soh_rotate((temporary(checksums) + dataframes[i+2,*]))
    endfor
  endelse

  return, checksums
end

function status_string, statusword
  str = 'Status:          ' + string(statusword, format='(I12)') + $
        '  56osc 91osc Rcvr Oven RecHtr WLHtr Doplr Dopdir'
  dopdir = (ishft(statusword, -4) and 1) ? 'Asc' : 'Dsc'
  dop    = (ishft(statusword, -5) and 1) ? ' On' : 'Off'
  osc56  = (ishft(statusword, -6) and 1) ? 'Pri' : 'Bak'
  osc91  = (ishft(statusword, -7) and 1) ? 'Pri' : 'Bak'
  rec    = (ishft(statusword, -8) and 1) ? ' On' : 'Off'
  oven   = (ishft(statusword, -9) and 1) ? 'Pri' : 'Bak'
  rechtr = (ishft(statusword, -10) and 1) ? 'Pri' : 'Bak'
  wrmhtr = (ishft(statusword, -11) and 1) ? 'Pri' : 'Bak'
  str = str + string(byte(10)) + $	; newline = byte 10
        '                                ' + osc56 + '   ' + $
        osc91 + '   ' + rec + '  ' + oven + '   ' + rechtr + '   ' + wrmhtr + $
        '   ' + dop + '    ' + dopdir
  return, str
end

;
; procedure to return 0 if input is even, 1 if odd
;

function isodd,num
  fnum=round(num)
  if (2*(fnum/2) eq fnum) then begin
    return,0
  end else begin
    return,1
  end

END

;
; procedure to save data
;

function data_save, inf, outf, header, docdata, wdata

  lastlat = 0.0d0
  lastlon = 0.0d0

  nfill = header.nfill
  ndata = header.ndata
  data = uintarr((ndata-nfill)/2)
  
  if (nfill gt 0) then fill = bytarr(nfill)
  readu, inf, docdata
  writeu, outf, docdata

  lat = (docdata.lat/8192.0d0)*!RADEG
  lon = (docdata.lon/8192.0d0)*!RADEG
  ntimes = docdata.stime / 1024.0
  lastlat = lat & lastlon = lon

  readu, inf, data
  writeu, outf, wdata
  if (nfill gt 0) then begin
   readu, inf, fill
   writeu, outf, fill
  endif

  return, "ok"
end

;
; Auxiliary procedure to process data stream
;

pro data_processing, header, words, infile, times, tf, outf, nrs, hdr, docdata
;
; Frame sync word
;
  fsw = '0F0F0F'XL
  fs1 = ishft(fsw, -12) and 4095
  fs2 = fsw and 4095
  nfill = header.nfill
  ndata = header.ndata
  tmpwords = uintarr(3,(ndata-nfill)/6,hdr.nrec)
  tdata = uintarr((ndata-nfill)/2)
  
  mask_1_4   = '000F'X
  mask_1_8   = '00FF'X
  mask_1_12  = '0FFF'X

  modenames = ['Undefined', 'Idle', 'Memory Dump', 'Normal', 'Early Orbit 1', $
    'Early Orbit 2a', 'Early Orbit 2b', 'Early Orbit 2c']

  eo2bc_hk = ['     Warm Load Temp 1', '     Warm Load Temp 2', $
              '     Warm Load Temp 3', '             WLE Temp', $
              '     Internal Ref PA1', '            Null data', $
              '        Temp Sensor 1', '        Temp Sensor 2', $
              '        Temp Sensor 3', '        Temp Sensor 4', $
              '        Temp Sensor 5', '        Temp Sensor 6', $
              '        Temp Sensor 7', '        Temp Sensor 8', $
              '        Temp Sensor 9', '       Temp Sensor 10', $
              '       Temp Sensor 11', '       Temp Sensor 12', $
              '       Temp Sensor 13', '       Temp Sensor 14', $
              '       Temp Sensor 15', '       Temp Sensor 16', $
              '       Temp Sensor 17', '       Temp Sensor 18', $
              '      WL Htr. current', '     PLO Oven current', $
              'Receiver Htr. current', '       PLO Lock Ind 1', $
              '       PLO Lock Ind 2', '       PLO Lock Ind 3']

  eo2b_ch  = ['Channel  1 ', 'Channel  6 ', 'Channel  8 ']
  eo2c_ch  = ['Channel 12 ', 'Channel 15 ', 'Channel 18 ']

  thisline = ''
  
  l = strlen(infile)
  stars = ''
  for i = 1L, l do stars = stars + '*' 

  firstframe = 0
  lastidx = n_elements(words) - 1

  index1 = where(words eq fs1, count)
  if (count le 0) then begin
    print, 'No valid SSMIS data frames found (1).'
    return
  endif

  notfirst = where(index1 ne 0, nnf)
  if (nnf le 0) then begin
    print, 'No valid SSMIS data frames found (2).'
    return
  endif
  index1 = index1[notfirst]

  notlast = where(index1 ne lastidx, nnl)

  if (nnl le 0) then begin
    print, 'No valid SSMIS data frames found (3).'
    return
  endif
  index1 = index1[notlast]

  index2f = where(words[index1+1] eq fs2, n2f)
  index2r = where(words[index1-1] eq fs2, n2r)
  if ((n2f le 0) and (n2r le 0)) then begin
    print, 'No valid SSMIS data frames found (4).'
    return
  endif

  if (n2r gt n2f) then begin
    swapstart = index1[index2r] - 2
    gezero = where(swapstart ge 0, gecount)
    if (gecount gt 0) then swapstart = swapstart[gezero] else begin
      print, 'No valid SSMIS data frames found (5).'
      return
    endelse

    nswaps = ulonarr(n_elements(swapstart))
    nsw = n_elements(swapstart) - 2
    for i = 0L, nsw do begin
      nswaps[i] = ((swapstart[i+1] - swapstart[i]) / 3L)
    endfor

    nsw = nsw + 1
    nswaps[nsw] = ((n_elements(words) - swapstart[nsw]) / 3L)

    for i = 0L, nsw do begin
      swap_ones = swapstart[i] + (lindgen(nswaps[i]) * 3)
      swap_threes = swap_ones + 2
      tmpkt = words[swap_ones]
      words[swap_ones] = words[swap_threes]
      words[swap_threes] = tmpkt
    endfor
  endif

  index1 = where(words eq fs1, count)
  if (count le 0) then begin
    print, 'No valid SSMIS data frames found (6).'
    firstframe = n_elements(words)
  endif else begin
    index2 = where(words[index1+1] eq fs2, count)
    if (count le 0) then begin
      print, 'No valid SSMIS data frames found (2).'
      firstframe = n_elements(words)
    endif else begin
      frames = index1[index2] + 2
      nframes = n_elements(index2) - 1
      firstframe = index1[index2[0]]
    endelse
  endelse

  errorno = 0
  catch, errorno
  if (errorno ne 0) then goto, word_error

  wcal = ulonarr(24)
  ccal = ulonarr(24)
  radb = ulonarr(24)
  rad2 = ulonarr(150)

  maxdigits = strcompress(strlen(strcompress(nframes+1, /rem)), /rem)
  scanno = 0L
  lastone = 0L
  psctim = 0L
  if (frames[nframes-1] gt (n_elements(words)-5)) then begin
    modes = [words[frames[0:nframes-2]+5] and 7, 0]
  endif else begin
    modes = words[frames+5] and 7
  endelse
  scans = where(modes gt 2, nscans)

  for i = 0L, nframes do begin
    nexti = i + 1
    mode = words[frames[i]+5] and 7

    if (mode gt 2) then scanno = scanno + 1
    istr = strcompress(scanno, /rem)

    if (keyword_set(split_scans)) then begin
      izero = string(i+1, format='(I' + maxdigits + '.' + maxdigits + ')')
    endif

    
    if (i eq 0) then begin
      for fill = 0L, firstframe-3, 3 do begin
        sec = 0
        if (fill mod 1185 lt 3) then begin
          sec = (fill / 1185) + 1
        endif
      endfor
      fmod = firstframe mod 3
    endif

    fst = frames[i] - 2

    if (mode gt 2) then begin
      sfidword = words[frames[i]]
      sfid = sfidword and 7
      print, i, frames[i] / 1185
            
      if (sfid eq 0) then begin
        fltver = string(ishft(sfidword and '01F0'X, -4), format='(I12)')
        serialno = string(ishft(sfidword and '0E00'X, -9), format='(I12)')
        fswcal = fltver
      endif else begin
        if (n_elements(fltver) eq 0) then fltver = '         N/A'
        if (n_elements(serialno) eq 0) then serialno = '         N/A'
      endelse

      if (sfid eq 1) then begin
        cal_beams = string(ishft(sfidword and '01F0'X, -4), format='(I12)')
        fswcal = cal_beams
      endif else begin
        if (n_elements(cal_beams) eq 0) then cal_beams = '         N/A'
      endelse

      if (sfid gt 1) then begin
        fswcal = string(ishft(sfidword and '01F0'X, -4), format='(I12)')
      endif

      cksum = ishft((words[frames[i]+1] and 4095), 6) or $
        ishft((words[frames[i]+2] and 4095), -6)
      
      sctim = ishft((long(words[frames[i]+2]) and 63), 12) or $
        (words[frames[i]+3] and 4095)
      psctim = ishft((long(words[frames[i+1]+2]) and 63), 12) or $
        (words[frames[i+1]+3] and 4095)
    
    endif
    nwords_mode = long([0, 14, 25491, 749, 389, 725, 725, 725]) * 3L
    nwords_mode[2] = 76471
    nwords = 0
    if (mode lt 8 and mode gt 0) then nwords = nwords_mode[mode]

    if (i lt nframes and nwords gt 0) then begin
      if (mode gt 2) then begin        
        next_cksum = ishft((words[frames[i+1]+1] and 4095), 6) or $
          ishft((words[frames[i+1]+2] and 4095), -6)
        cmp_cksum = ssmis_compute_checksum(words[frames[i]-2:frames[i]+nwords-3])
      endif
    endif

    case mode of
;
; Idle mode
;
      1: begin
        sfidword = words[frames[i]]
	      idle = reverse(reform(words[frames[i]-2:frames[i]+39], 3, 14), 1)
        print, i, frames[i] / 1185
      end
;
; Memory dump mode
;
      2: begin
        sfidword = words[frames[i]]
        print, i, frames[i] / 1185

        dw1 = frames[i] - 2
        dw2 = dw1 + 76475
        memory = reform(words[dw1:dw2], 3, 25492)

        ; Undo previous word swapping
        index1 = where(memory eq fs1, count)
        index2f = where(memory[index1+1] eq fs2, n2f)
        if (n2f gt 0) then begin
          swapstart = index1[index2f]
          nswaps = ulonarr(n_elements(swapstart))
          nsw = n_elements(swapstart) - 2
          for mw = 0L, nsw do begin
            nswaps[mw] = ((swapstart[mw+1] - swapstart[mw]) / 3L)
          endfor

          nsw = nsw + 1
          nswaps[nsw] = ((n_elements(memory) - swapstart[nsw]) / 3L)

          for mw = 0L, nsw do begin
            swap_ones = swapstart[mw] + (lindgen(nswaps[mw]) * 3)
            swap_threes = swap_ones + 2
            tmpkt = memory[swap_ones]
            memory[swap_ones] = memory[swap_threes]
            memory[swap_threes] = tmpkt
          endfor
          memory = memory[*,3:25491]
        endif else begin
          memory = reform(words[frames[i]+7:frames[i]+76473], 3, 25489)
        endelse

        triple = uintarr(3, 19115)
        quad = uintarr(4, 19115)
        quad[0:76459] = memory[0:76459]
        triple[0, *] = ishft(quad[0, *], 4) or (ishft(quad[1, *], -8) and mask_1_4)
        triple[1, *] = ishft(quad[1, *], 8) or (ishft(quad[2, *], -4) and mask_1_8)
        triple[2, *] = ishft(quad[2, *], 12) or (quad[3, *] and mask_1_12)
        cksum = ishft(memory[76460], 4) or ishft(memory[76461], -8)
        cmp_cksum = ssmis_compute_checksum(reform(triple, 57345, 1), /no_rev)

	; Skip any frame syncs found in memory as they are not real scans/frames
	nextframe = min(where(frames gt frames[i]+76468))
	if (nextframe gt i) then nexti = nextframe
      end
;
; Normal mode
;
      3: begin
        for j = 0, 11 do begin
          wcal[(j*2)] = ishft((words[frames[i]+13+(j*3)] and 4095), 6) or $
                        ishft((words[frames[i]+14+(j*3)] and 4095), -6) xor 32768
          wcal[(j*2)+1] = ishft((words[frames[i]+14+(j*3)] and 63), 12) or $
                          (words[frames[i]+15+(j*3)] and 4095) xor 32768
          ccal[(j*2)] = ishft((words[frames[i]+49+(j*3)] and 4095), 6) or $
                        ishft((words[frames[i]+50+(j*3)] and 4095), -6) xor 32768
          ccal[(j*2)+1] = ishft((words[frames[i]+50+(j*3)] and 63), 12) or $
                          (words[frames[i]+51+(j*3)] and 4095) xor 32768
        endfor
        
        for j = 0, 29 do begin
          r1 = fix(101 * randomu(Seed, 27) - 50)
          if (j ge 0) and (j lt 20) then begin
             odd = isodd(j)
             ri = 8 + (j/2)
             fline = 85
             ii = 0
             if (odd eq 0) then begin
               for rnum = 0, 1 do begin
                 words[frames[i]+fline+3*rnum+(72*j)] = ccal[ri] + r1[ii++]
                 words[frames[i]+fline+3*rnum+1+(72*j)] = ccal[ri]+ r1[ii++]
                 words[frames[i]+fline+3*rnum+2+(72*j)] = ccal[ri] + r1[ii++]
               endfor
               
               for rnum = 17, 23 do begin
                 words[frames[i]+fline+3*rnum+(72*j)] = ccal[ri] + r1[ii++]
                 words[frames[i]+fline+3*rnum+1+(72*j)] = ccal[ri] + r1[ii++]
                 words[frames[i]+fline+3*rnum+2+(72*j)] = ccal[ri] + r1[ii++]
               endfor

             endif else begin
               for rnum = 0, 1 do begin
                 words[frames[i]+fline+3*rnum+(72*j)] = wcal[ri] + r1[ii++]
                 words[frames[i]+fline+3*rnum+1+(72*j)] = wcal[ri] + r1[ii++]
                 words[frames[i]+fline+3*rnum+2+(72*j)] = wcal[ri] + r1[ii++]
               endfor
               
               for rnum = 17, 23 do begin
                 words[frames[i]+fline+3*rnum+(72*j)] = wcal[ri] + r1[ii++]
                 words[frames[i]+fline+3*rnum+1+(72*j)] = wcal[ri] + r1[ii++]
                 words[frames[i]+fline+3*rnum+2+(72*j)] = wcal[ri] + r1[ii++]
               endfor
             endelse
          endif

          
          if (j eq 29) then begin
            t_cksum = ssmis_compute_checksum(words[frames[i]-2:frames[i]+nwords-3])                                                
            words[frames[i+1]+2] = ishft(t_cksum and 63, 6) or (ishft(sctim, -12) and 63)
            words[frames[i+1]+1] = ishft(t_cksum, -6) and 4095                      
            t_next_cksum = ishft((words[frames[i+1]+1] and 4095), 6) or $
              ishft((words[frames[i+1]+2] and 4095), -6)
            t_cksum = ssmis_compute_checksum(words[frames[i]-2:frames[i]+nwords-3]) 
            cf = frames[i] / 1185
            if (i eq nframes-1) then begin
              for tn = lastone, nrs do begin
                tmptest = words[*,*,tn]
                tmpwords[*,*,nrs-tn] = tmptest
              endfor
            endif else begin
              for tn = lastone, cf do begin
                tmptest = words[*,*,tn]
                tmpwords[*,*,nrs-tn] = tmptest
              endfor
            endelse              

            lastone = cf + 1
          endif    
        endfor
      end
;
; Early Orbit 1
;
      4: begin
        for j = 0, 11 do begin
          wcal[(j*2)] = ishft((words[frames[i]+13+(j*3)] and 4095), 6) or $
                        ishft((words[frames[i]+14+(j*3)] and 4095), -6) xor 32768
          wcal[(j*2)+1] = ishft((words[frames[i]+14+(j*3)] and 63), 12) or $
                          (words[frames[i]+15+(j*3)] and 4095) xor 32768
          ccal[(j*2)] = ishft((words[frames[i]+49+(j*3)] and 4095), 6) or $
                        ishft((words[frames[i]+50+(j*3)] and 4095), -6) xor 32768
          ccal[(j*2)+1] = ishft((words[frames[i]+50+(j*3)] and 63), 12) or $
                          (words[frames[i]+51+(j*3)] and 4095) xor 32768
        endfor
        for j = 0, 29 do begin
          for k = 0, 11 do begin
            radb[(k*2)] = ishft((words[frames[i]+85+(36*j)+(k*3)] and 4095), 6) or $
                          ishft((words[frames[i]+86+(36*j)+(k*3)] and 4095), -6) xor 32768
            radb[(k*2)+1] = ishft((words[frames[i]+86+(36*j)+(k*3)] and 63), 12) or $
                            (words[frames[i]+87+(36*j)+(k*3)] and 4095) xor 32768
          endfor
        endfor
      end
;
; Early Orbit 2a
;
      5: begin
        if (sfid eq 7) then begin
          lastj = 29
          nwords = 365*3
        endif else begin
          lastj = 59
        endelse
        bpoffset = sfid * 60

        if (keyword_set(special)) then begin
          triplets = ((nwords/3L) - 5) ;/ 3
          for t = 1L, triplets do begin
            triplet = words[frames[i]+10+3*t:frames[i]+12+3*t] * 2
            diff = (7110 + fix(triplet[1]) - fix(triplet[2])) mod 7110
            txt = ''
            if (diff lt 100) then txt = '   low'
            if (diff lt 10) then txt = '   LOW!'
          endfor
        endif else begin
          for j = 0L, lastj do begin
            for k = 0, 11 do begin
              radb[(k*2)] = ishft((words[frames[i]+13+(36*j)+(k*3)] and 4095), 6) or $
                            ishft((words[frames[i]+14+(36*j)+(k*3)] and 4095), -6) xor 32768
              radb[(k*2)+1] = ishft((words[frames[i]+14+(36*j)+(k*3)] and 63), 12) or $
                              (words[frames[i]+15+(36*j)+(k*3)] and 4095) xor 32768
            endfor
          endfor
        endelse
      end
;
; Early Orbit 2b
;
      6: begin
        for j = 0, 2 do begin
          for k = 0, 14 do begin
            hk1 = ishft((words[frames[i]+13+(3*k)+(720*j)] and 4095), 6) or $
                  ishft((words[frames[i]+14+(3*k)+(720*j)] and 4095), -6) $
                  xor 32768
            hk1 = ishft(temporary(hk1), -4) and 4095
            hk2 = ishft((words[frames[i]+14+(3*k)+(720*j)] and 63), 12) or $
                  (words[frames[i]+15+(3*k)+(720*j)] and 4095) xor 32768
            hk2 = ishft(temporary(hk2), -4) and 4095
          endfor
          for l = 0, 2 do begin
            sec = 0
            for m = 0, 14 do begin
              for k = m*5, (m*5)+4 do begin
                st = frames[i]+58+(3*k)+(720*j)+(225*l)
                if (st mod 1185 lt 3) then begin
                  sec = (st / 1185) + 1
                  pos = 1 + ((k - (m*5)) * 2)
                  triplet = words[st:st+2]
                endif
                rad2[k*2] = ishft((words[frames[i]+58+(3*k)+(720*j)+(225*l)] and 4095), 6) or $
                      ishft((words[frames[i]+59+(3*k)+(720*j)+(225*l)] and 4095), -6) xor 32768
                rad2[(k*2)+1] = ishft((words[frames[i]+59+(3*k)+(720*j)+(225*l)] and 63), 12) or $
                      (words[frames[i]+60+(3*k)+(720*j)+(225*l)] and 4095) xor 32768
                thisline = string(rad2[m*10:(k*2)+1], format='('+strcompress((k+1-(m*5))*2,/rem)+'I8)')
              endfor
              thisline = ''
              sec = 0
            endfor
          endfor
        endfor
      end
;
; Early Orbit 2c
;
      7: begin
        for j = 0, 2 do begin
          for k = 0, 14 do begin
            hk1 = ishft((words[frames[i]+13+(3*k)+(720*j)] and 4095), 6) or $
                  ishft((words[frames[i]+14+(3*k)+(720*j)] and 4095), -6) $
                  xor 32768
            hk1 = ishft(temporary(hk1), -4) and 4095
            hk2 = ishft((words[frames[i]+14+(3*k)+(720*j)] and 63), 12) or $
                  (words[frames[i]+15+(3*k)+(720*j)] and 4095) xor 32768
            hk2 = ishft(temporary(hk2), -4) and 4095
          endfor
          for l = 0, 2 do begin
            sec = 0
            for m = 0, 14 do begin
              for k = m*5, (m*5)+4 do begin
                st = frames[i]+58+(3*k)+(720*j)+(225*l)
                if (st mod 1185 lt 3) then begin
                  sec = (st / 1185) + 1
                  pos = 1 + ((k - (m*5)) * 2)
                  triplet = words[st:st+2]
                endif
                rad2[k*2] = ishft((words[frames[i]+58+(3*k)+(720*j)+(225*l)] and 4095), 6) or $
                      ishft((words[frames[i]+59+(3*k)+(720*j)+(225*l)] and 4095), -6) xor 32768
                rad2[(k*2)+1] = ishft((words[frames[i]+59+(3*k)+(720*j)+(225*l)] and 63), 12) or $
                      (words[frames[i]+60+(3*k)+(720*j)+(225*l)] and 4095) xor 32768
                thisline = string(rad2[m*10:(k*2)+1], format='('+strcompress((k+1-(m*5))*2,/rem)+'I8)')
              endfor
              thisline = ''
              sec = 0
            endfor
          endfor
        endfor
      end
      else:
    endcase

; Output fill words
    if (i lt nframes) then nextstart = frames[nexti] $
    else nextstart = n_elements(words)
    nfill = nextstart - frames[i] - nwords
    if (nfill lt 0) then begin
      print, '**** ERROR! ****'
    endif else begin
      for fill = 1L, nfill, 3 do begin
        st = frames[i]+nwords+fill-3
        en = (st + 2) < (nextstart - 3)
        sec = 0
        if (st mod 1185 lt 3) then begin
          sec = (st / 1185) + 1
        endif
      endfor

    endelse

    i = nexti - 1	; In case we skipped bogus frame syncs in Memory Dump

  endfor

  word_error:
  catch, /cancel
  
  if (thisline ne '') then print, thisline

  for i = 0L, nrs do begin
    fdata = tmpwords[*,*, i]
    ret_test = data_save(tf, outf, hdr, docdata, fdata)
  endfor
end

;
; Main test_data_generation procedure
; Note: It is for special customized software testing only!
;
pro test_data_generation, infile, outfile
  if (n_params() lt 2) then begin
    print, 'Usage: test_data_generation, infile, outfile],'
    return
  endif
  
  header = { RSDRHeaderV8, $
             id:            '    ', $
             readoutrev:    0L, $
             beginrev:      0L, $
             endrev:        0L, $
             rplus:         0L, $
             inclination:   0,  $
             nodalyear:     0u, $
             nodalday:      0u, $
             nodalhour:     0u, $
             nodalmin:      0u, $
             nodalsec:      0u, $
             nodallon:      0L, $
             starttime:     0L, $
             stoptime:      0L, $
             nrec:          0L, $
             ninvalid:      0L, $
             ndata:         0L, $
             nfill:         0u, $
             datadate:      0u, $
             rsdrver:       0u, $
             blank1:        bytarr(2), $
             rightasc:      0L, $
             special:       uintarr(12), $
             blank2:        bytarr(8) $
  }

  header7 = { RSDRHeader, $
             id:'    ', $
             readoutrev:0L, $
             beginrev:0L, $
             endrev:0L, $
             rplus:0L, $
             nodalyear:0u, $
             nodalday:0u, $
             nodalhour:0u, $
             nodalmin:0u, $
             startfiducial:0L, $
             stopfiducial:0L, $
             nrec:0L, $
             ninvalid:0L, $
             ndata:0L, $
             nfill:0u, $
             special:intarr(12), $
             nodalsec:0u, $
             blank:bytarr(4) $
  }

  docdata = { RSDRDocV8, $
              valid:      0, $
              lat:        0, $
              lon:        0L, $
              sath:       0L, $
              quarter:    0, $
              angle:      0, $
              alt:        0UL, $
              etime:      0UL, $
              stime:      0UL, $
              zbits:      lonarr(5), $
              ebits:      0L, $
              cbits:      0u, $
              gbits:      0u, $
              hbits:      0u, $
              ibits:      0u, $
              mbits:      0u, $
              pbits:      0u, $
              qbits_line: 0u, $
              qbits_sub:  0u, $
              ybits:      0u, $
              blank:      bytarr(30) $
  }

  docdata7 = { RSDRDoc, $
              valid:0, $
              lat:0, $
              lon:0u, $
              angle:0u, $
              alt:0UL, $
              etime:0UL, $
              stime:0UL, $
              zbits:lonarr(5), $
              ebits:0L, $
              cbits:0u, $
              gbits:0u, $
              hbits:0u, $
              ibits:0u, $
              mbits:0u, $
              pbits:0u, $
              qbits_line:0u, $
              qbits_sub:0u, $
              ybits:0u, $
              blank:bytarr(18) $
  }
  
  tmpfile = FILE_BASENAME(infile, '.dat') + '_tmp.dat'
  file_delete, outfile, /allow_nonexistent
  file_delete, tmpfile, /allow_nonexistent
  
  openr, in, infile, /get_lun, /swap_if_little_endian
  readu, in, header  
  openw, fout, outfile, /get_lun, /swap_endian
  
  file_copy, infile, tmpfile,  /overwrite
  openr, tmpf, tmpfile, /get_lun, /swap_if_little_endian
  readu, tmpf, header
  writeu, fout, header

  if ((header.rsdrver ne 8) and (header.rsdrver ne 10)) then begin
    rsdrstat = fstat(in)
    if (rsdrstat.size mod 2452 eq 0) then begin
      point_lun, in, 0
      header = header7
      docdata = docdata7
      readu, in, header
      readu, tmpf, header
      writeu, fout, header
    endif
    nrec_size = (rsdrstat.size / 2372) - 1
    if (nrec_size lt header.nrec) then begin
      print, 'Adjusting nrec from ' + strcompress(header.nrec, /rem) + ' to ' $
        + strcompress(nrec_size, /rem)
      header.nrec = nrec_size
    endif
  endif
  if (header.ndata eq 2370 && header.nfill eq 2) then header.ndata = 2372
  if (n_elements(ovrfill) gt 0) then nfill = ovrfill else nfill = header.nfill
  if (n_elements(ovrdata) gt 0) then ndata = ovrdata else ndata = header.ndata
  data = uintarr((ndata-nfill)/2)
  words = uintarr(3,(ndata-nfill)/6,header.nrec)

  times = dblarr(header.nrec)
  if (nfill gt 0) then fill = bytarr(nfill)
  readu, in, data
  readu, tmpf, data
  writeu, fout, data
  if (nfill gt 0) then begin
    readu, in, fill
    readu, tmpf, fill
    writeu, fout, fill
  endif
  nr = header.nrec - 1
  lastlat = 0.0d0
  lastlon = 0.0d0
  indwords = ulonarr(header.nrec)
  for i = 0L, nr do begin
    readu, in, docdata        
    lat = (docdata.lat/8192.0d0)*!RADEG
    lon = (docdata.lon/8192.0d0)*!RADEG
    times[nr-i] = docdata.stime / 1024.0
    print, times[nr-i], lat, lon, lat-lastlat, lon-lastlon
    lastlat = lat & lastlon = lon    
    readu, in, data
    words[*,*,nr-i] = data    ; assume time-reversed 1-second packets
    indexl = ((nr-i-1)*(ndata-nfill)/2)
    indexh = ((nr-i)*(ndata-nfill)/2)
    dims = size(words, /dimensions)
    indwords[i] = dims[0]*dims[1]*(nr-i)
    
    if (nfill gt 0) then begin
      readu, in, fill
    endif
  endfor
  
  lwords = size(data, /n_elements)
  iwords=Where(words mod lwords eq 0)
  free_lun, in
  mintest = where(indwords eq min(indwords))
  
  if (n_elements(complement_2a) eq 0) then complement_2a = 1
  
  data_processing, header,words,infile,times,tmpf,fout,nr,header,docdata

  close, tmpf
  close, fout
  
  file_delete, tmpfile, /allow_nonexistent
 
end
############################################################################
#automis.py
from sgp4.earth_gravity import wgs84
from sgp4.io import twoline2rv
from skyfield.api import load, EarthSatellite
from skyfield.framelib import itrs
from datetime import datetime, timezone
from datetime import timedelta
from urllib.request import urlopen, pathname2url
import sys, os
from skyfield.iokit import parse_tle_file
from io import BytesIO
from sgp4.api import Satrec
from sgp4.api import jday
from sgp4.api import days2mdhms
from sgp4.conveniences import sat_epoch_datetime
import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt
import datetime as dtt
from datetime import timedelta
from pyproj import CRS, Transformer
import math
import time
from urllib.parse import urljoin
import glob
import re
import math
import subprocess

sdir = os.path.dirname(os.path.abspath(__file__)) + "/data/"
tdir = os.path.dirname(os.path.abspath(__file__)) + "/geotestlog/"
maxnumrev = 6000
# haversine formula to get the circle distance between two points (unit in degrees)
def haversine(lon1, lat1, lon2, lat2):
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    # Radius of earth in kilometers is 6371
    km = 6371*c
    return km

# get the circle distance between two points on the earth (unit in degrees)
def dist(lat1, long1, lat2, long2):
    # convert decimal degrees to radians 
    lat1, long1, lat2, long2 = map(radians, [lat1, long1, lat2, long2])
    # haversine formula 
    dlon = long2 - long1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    # Radius of earth in kilometers is 6371
    km = 6371* c
    return km

# find the distance of two geo locations
def find_dist(lat, lon, refdata):
    distances = refdata.apply(
        lambda row: dist(lat, lon, row['latitude(degree)'], row['longitude(degree)']), 
        axis=1)
    return refdata.loc[distances.idxmin(), 'name']

# Converts ECEF (x, y, z) coordinates to latitude, longitude, and altitude.
def xyz_to_lla(x, y, z, crs_in='EPSG:4978', crs_out='EPSG:4326'):
    transformer = Transformer.from_crs(crs_in, crs_out, always_xy=True)
    lon, lat, alt = transformer.transform(x, y, z)
    return lat, lon, alt

# get tle information
def get_tle(lines, n, key, zeroline, lst):
    i = 0
    sch=''
    while i < n:
        ll = lines[i]
        if key in ll: 
           ll0 = lines[i]
           ll1 = lines[i+1] 
           ll2 = lines[i+2]
           if(zeroline == 0):
              sch = ll.strip()+ '\n' + ll1.strip() + '\n' + ll2.strip()
              if lst == 1:
                  sch = sch.splitlines()
           else:
              sch = ll1.strip() + '\n' + ll2.strip()
              if lst == 1:
                  sch = sch.splitlines()
           i += 2
        i += 1
    return sch

def getnums(string):
     numstr = re.findall(r'\d+', string)
     intnum = [int(item) for item in numstr]
     return intnum

def findfiles(path, pat, keys):
    nofile = "skip"
    matchfiles = os.path.join(path, pat)
    pp = glob.glob(matchfiles)
#    print(pp)
    minn=9999999
    retl=''
    retf = ''   
    for index, item in enumerate(pp):
        ff = os.path.basename(pp[index])
        ll = getnums(ff)
#lc test        if (keys-ll[0]) < minn and (keys-ll[0]) > 0 and (keys-ll[0]) < 110:
        if abs(keys-ll[0]) < minn and abs(keys-ll[0]) < maxnumrev:
            minn = keys-ll[0]
            retf = ff
            retl = ll[0]
            print(ll[0])
    return minn, retl, retf

def extract_number(f):
    s = re.findall("\\d+$",f)
    return (int(s[0]) if s else -1,f)

# get orbit information
def geo_info(sat, mtime, us_inc, num_samples, line1, line2, fname, deci, minn):

    output_filename = sat.strip() + "" + \
            mtime.strftime("%Y_%m_%d_%H_%M_%S_%f") \
            + ".csv"
    output_filename = output_filename.replace(" ", "_").replace("(", "_")\
            .replace(")", "_").replace("/", "_")\
            .replace("[", "_").replace("]", "_")
            
    outpath = tdir + output_filename
    
    outfile = open(outpath, "w")
    outfile.write("year, " + "month, "+ "day, " + "hour, " + "min, " + "sec, "+ "itlat, " + "itlon, " + "italt," + "rev#" + "\n");

    satellite = twoline2rv(line1, line2, wgs84)
    
    orbit_number = int(line2[63:63 + 5])  # Get the orbit number.
    print(orbit_number)
    
    tss = load.timescale()
    filep = sdir + fname 
    if os.path.exists(filep):
        print(filep)
    else:
        print(f"File '{filep}' does not exist.")    
##        exit(1)
        return "skipped"
    with load.open(filep) as ff:
        skysatellites = list(parse_tle_file(ff, tss))
        
    if skysatellites:
        print(f"Loaded {len(skysatellites)} skysatellites.")
        print(f"First satellite: {skysatellites[0].name}")
    
    # Define a time for position calculation
    ttt = tss.utc(datetime.now(timezone.utc))
    
    # Example: Access a satellite by name (if available in the TLE)
    ssat = skysatellites[0]
    # print(ssat)

    # Calculate position
    geocentric = ssat.at(ttt)
    
    # Get position in various coordinates
    # print(f"Satellite: {ssat.name}")
    # print(f"Position (km, GCRS): {geocentric.position.km}")
    # print(f"Velocity (km/s, GCRS): {geocentric.velocity.km_per_s}")

    epoch_year = line1[18:20]
    tle_epoch_year = 2000 + int(epoch_year)
    tle_epoch_day = float(line1[20:32])
    tle_epoch_datetime = datetime(tle_epoch_year, 1, 1) + timedelta(days=tle_epoch_day - 1)
    # Get the revolution number at the TLE epoch
    rev_at_epoch = int(line2[63:68])
    mean_motion_str = line2[52:63]
    mean_motion = float(mean_motion_str)
    print(mean_motion)

    mtime = mtime + timedelta(hours=(24/mean_motion)*(minn-1), minutes=0)
    
    for i in range(0, num_samples, deci):
        datestamp = mtime.strftime("%Y,%m,%d,%H,%M,%S.%f")
        target_time = datetime(mtime.year, mtime.month, mtime.day, mtime.hour, mtime.minute, mtime.second)        
        time_diff_days = (target_time - tle_epoch_datetime).total_seconds() / (24 * 3600)
        rev_since_epoch = mean_motion * time_diff_days
        rev_t = rev_at_epoch + round(rev_since_epoch)
        if i == 0:
            revst = rev_t
        
        if i == (num_samples-1):
            reved = rev_t
               
        second = float(str(mtime.second) + "." + str(mtime.microsecond))
        position, v = satellite.propagate(mtime.year, mtime.month, mtime.day, \
                mtime.hour, mtime.minute, second)

        revnum = satellite.revnum
        tsss = tss.utc(mtime.year, mtime.month, mtime.day, mtime.hour, mtime.minute, mtime.second)
        geocentric = ssat.at(tsss)
        position_itrs = geocentric.frame_xyz(itrs).km    
        itlat, itlon, italt = xyz_to_lla(position_itrs[0]*1000,position_itrs[1]*1000, position_itrs[2]*1000)
        position_string = ","
        latitude, longitude, altitude = xyz_to_lla(position[0]*1000, position[1]*1000, position[2]*1000)   
        position_string += " "
        position_string += str(itlat) + ","
        position_string += " "        
        position_string += str(itlon) + ","
        position_string += " "
        position_string += str(italt) + ","
        position_string += " "
        position_string += str(rev_t) 
        
        outfile.write(datestamp + position_string + "\n");
        mtime = mtime + timedelta(microseconds=us_inc)*deci
        reved = rev_t

    outfile.close()
    ff.close()
    dirname, basefile = os.path.split(outpath)
    newname = str(revst) + "-" + str(reved) + "-" + basefile
    if os.path.exists(os.path.join(dirname, newname)):
        os.remove(os.path.join(dirname, newname))
    os.rename(outpath, os.path.join(dirname, newname))
    retout = os.path.join(dirname, newname)
    print("retout ", retout)
    return retout
    
def misproc(file_path):
    noforbidden = True
    f16="DMSP 5D-3 F16"
    f17="DMSP 5D-3 F17"
    f18="DMSP 5D-3 F18"
    tle_stringf16 = []
    tle_stringf17 = []
    tle_stringf18 = []
    nzero = 0
    epochf = 0
    infile = 0
    line1 = ""
    line2 = ""
    nline = 0
    tle_fstring = [''] * 3
    tle_filename = ""
    altmis = True
    minn = 0
    satinfo = "skipped"

    if altmis:
        print(file_path)
        base = os.path.dirname(file_path)
        basename = os.path.basename(file_path)
        tmpstr = (basename.split(".")[0])[3:] 
        keys = int(tmpstr.split("_")[0])   
        flt=basename[0:3]
                
        fpath = "./data"
        pat = "tle_"+"*"+flt+"*.csv" 
        base = os.path.dirname(os.path.abspath(__file__)) + "/data/"
        minn, retl, retf = findfiles(base, pat, keys)
        if minn == 9999999:
            print(keys, " skipped!")
            return satinfo
        else:
            print(minn, retl, retf, keys)

        file_url = "file:///" + (os.path.join(base, retf)).replace("\\", "/")
        html = urlopen(file_url)
        with urlopen(file_url) as response:
            lines_bytes = html.readlines()
            lines_str = [line.decode('utf-8') for line in lines_bytes]
            noforbidden = True

    print(noforbidden)
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(tdir, exist_ok=True)
    if noforbidden:
        if altmis:
            lens = len(lines_str)
            start_time = time.perf_counter() 

        if altmis:
            flt_string = [flt]
        else:
            flt_string = [f16, f17, f18]

        for i in range(len(flt_string)):
            flt_str = get_tle(lines_str, lens, flt_string[i], 0, 1)
            line2 = flt_str[2].strip()
            line1 = flt_str[1].strip()
            line0 = flt_str[0].strip()
            sat = line0
            tle_string = flt_str[0].strip()+ '\n' + flt_str[1].strip() + '\n' + flt_str[2].strip() 
            epoch_year = line1[18:20]
            epoch_day = float(line1[20:32])
            epoch = np.datetime64(dtt.datetime.strptime(epoch_year, "%y") + dtt.timedelta(days=epoch_day - 1), "us")
            rep = str.maketrans({":": "_", ".": "_", " ": "_"})
            epoch = str(epoch).translate(rep)
            satstr = (line0.strip()).replace(" ", "_").replace("(", "_")\
                .replace(")", "_").replace("/", "_")\
                .replace("[", "_").replace("]", "_")                          
        
            dltime = time.strftime("%Y-%m-%d %H:%M:%S")
            dltime = str(dltime).translate(rep)
            tle_filename = "tle_" + line2[63:68] + "_" + satstr + str(epoch) + ".csv"
            tle_str = open(sdir + tle_filename, "w")
            tle_str.write(tle_string)     
            tle_str.close()   
            
            satellite2 = Satrec.twoline2rv(line1, line2)
            if(int(epochf) == 1):
                month, day, hour, minute, second = days2mdhms(satellite2.epochyr, satellite2.epochdays)
                start = str(20)+str(satellite2.epochyr)+' '+str(month)+' '+str(day)+' '+str(hour)+' '+ \
                    str(minute)+' '+str(second).split('.')[0]+' '+str(second).split('.')[1]
            else:
                month, day, hour, minute, second = days2mdhms(satellite2.epochyr, satellite2.epochdays)
                #adjustment
                #hour = 23
                #hour = 0
                #day = day - 1
                #minute = 1                
                start = str(20)+str(satellite2.epochyr)+' '+str(month)+' '+str(day)+' '+str(hour)+' '+ \
                    str(minute)+' '+str(second).split('.')[0]+' '+str(second).split('.')[1]
            
            inc = 1           
            us_inc = inc
            us_inc = us_inc * 1e6
            num_samples = int(86400) #24hr
            if altmis:
                num_samples = int(18000) #5hr
###test only
##                num_samples = int(1800)
        
            time2 = datetime.strptime(start.strip(), "%Y %m %d %H %M %S %f")
            tledl = False
            deci = 1
            if not tledl:    
                satinfo = geo_info(sat, time2, us_inc, num_samples, line1, line2, tle_filename, deci, minn)
            
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            print(f"Elapsed time: {elapsed_time:.6f} seconds")                     
           
    print ("done")
    print(satinfo)
    return satinfo
#####################################################
#cpnwkfiles.py
import shutil
import os

# Define the source and destination paths using raw strings (r'')
# Use double backslashes or forward slashes for network paths (UNC paths)
# Format: r'\\ServerName\ShareName\path\to\file.ext'

source_file = r'\\Sd78mda02.northgrum.com\tgroups\B\Block-5\Data\PrepGen Processing\.MS Files of the day\2025\Dec\2025.12.09\F1614253.MS'
destination_folder = r'C:/Users/M26814/Downloads/misout'
destination_file = os.path.join(destination_folder, os.path.basename(source_file))

try:
    # Use shutil.copy() to copy the file to a directory
    shutil.copy(source_file, destination_folder)
    print(f"Successfully copied '{source_file}' to '{destination_folder}'")

    # Alternatively, use shutil.copyfile() if you want to specify the exact destination file name
    # shutil.copyfile(source_file, destination_file)
    # print(f"Successfully copied '{source_file}' to '{destination_file}'")

except FileNotFoundError:
    print("Error: Source file or destination directory not found.")
except PermissionError:
    print("Error: Permission denied. Check network share access and user credentials.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
###################################################
//functions.c
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "functions.h"

void write_little_endian_16(FILE *fp, uint16_t value) {
	uint8_t lsb = (value) & 0xFF;
	uint8_t msb = (value >> 8) & 0xFF;
	fwrite(&lsb, sizeof(uint8_t), 1, fp);
	fwrite(&msb, sizeof(uint8_t), 1, fp);
}

void write12(int *N, int *K) {
	int I;
	word tempw, tempw1, tempw2;
	unsigned short result;
	bool ff = true;

	for (I = 1; I <= 750; I++) {
		tempw = Bufdat[*N];
		(*N)++;
		if ((*N >= 9000) && ff) break;
		result = (int)tempw;
		tempw1 = (result >> 4) & 0x0FFF;
		Buf12[*K] = tempw1;
		(*K)++;

		tempw2 = Bufdat[*N];
		(*N)++;
		if ((*N >= 9000) && ff) break;
		result = (int)tempw;
		tempw = (result << 8) & 0x0F00;
		result = (int)tempw2;
		tempw1 = result >> 8;
		tempw = (tempw1 + tempw) & 0x0FFF;
		Buf12[*K] = tempw;
		(*K)++;

		result = (int)tempw2;
		tempw = (result << 4) & 0x0FF0;
		tempw2 = Bufdat[*N];
		(*N)++;
		if ((*N >= 9000) && ff) break;
		result = (int)tempw2;
		tempw1 = result >> 12;
		tempw = (tempw + tempw1) & 0x0FFF;
		Buf12[*K] = tempw;
		(*K)++;

		result = (int)tempw2;
		tempw = result & 0x0FFF;
		Buf12[*K] = tempw;
		(*K)++;
	}
}

void scales(int kmax) {
	int I, N, K;
	word tempw;
	int mintemp;
	bool ff = true;

	K = 87;
	if (kmax > K) {
		for (N = 1; N <= 30; N++) {
			// beam position N

			// ch 8 - 6 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[8] = tempw;
				maxb[8] = tempw;
			}
			else {
				if (tempw < minb[8]) minb[8] = tempw;
				if (tempw > maxb[8]) maxb[8] = tempw;
			}
			// get pix 2 to 6
			for (I = 1; I <= 5; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[8]) minb[8] = tempw;
				if (tempw > maxb[8]) maxb[8] = tempw;
			}

			// ch 9 - 6 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[9] = tempw;
				maxb[9] = tempw;
			}
			else {
				if (tempw < minb[9]) minb[9] = tempw;
				if (tempw > maxb[9]) maxb[9] = tempw;
			}
			// get pix 2 to 6
			for (I = 1; I <= 5; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[9]) minb[9] = tempw;
				if (tempw > maxb[9]) maxb[9] = tempw;
			}

			// ch 10 - 6 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[10] = tempw;
				maxb[10] = tempw;
			}
			else {
				if (tempw < minb[10]) minb[10] = tempw;
				if (tempw > maxb[10]) maxb[10] = tempw;
			}
			// get pix 2 to 6
			for (I = 1; I <= 5; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[10]) minb[10] = tempw;
				if (tempw > maxb[10]) maxb[10] = tempw;
			}

			// ch 11 - 6 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[11] = tempw;
				maxb[11] = tempw;
			}
			else {
				if (tempw < minb[11]) minb[11] = tempw;
				if (tempw > maxb[11]) maxb[11] = tempw;
			}
			// get pix 2 to 6
			for (I = 1; I <= 5; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[11]) minb[11] = tempw;
				if (tempw > maxb[11]) maxb[11] = tempw;
			}

			// ch 17 - 6 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[17] = tempw;
				maxb[17] = tempw;
			}
			else {
				if (tempw < minb[17]) minb[17] = tempw;
				if (tempw > maxb[17]) maxb[17] = tempw;
			}
			// get pix 2 to 6
			for (I = 1; I <= 5; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[17]) minb[17] = tempw;
				if (tempw > maxb[17]) maxb[17] = tempw;
			}

			// ch 18 - 6 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[18] = tempw;
				maxb[18] = tempw;
			}
			else {
				if (tempw < minb[18]) minb[18] = tempw;
				if (tempw > maxb[18]) maxb[18] = tempw;
			}
			// get pix 2 to 6
			for (I = 1; I <= 5; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[18]) minb[18] = tempw;
				if (tempw > maxb[18]) maxb[18] = tempw;
			}

			// ch 12 - 3 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[12] = tempw;
				maxb[12] = tempw;
			}
			else {
				if (tempw < minb[12]) minb[12] = tempw;
				if (tempw > maxb[12]) maxb[12] = tempw;
			}
			// get pix 2 to 3
			for (I = 1; I <= 2; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[12]) minb[12] = tempw;
				if (tempw > maxb[12]) maxb[12] = tempw;
			}
			// ch 13 - 3 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[13] = tempw;
				maxb[13] = tempw;
			}
			else {
				if (tempw < minb[13]) minb[13] = tempw;
				if (tempw > maxb[13]) maxb[13] = tempw;
			}
			// get pix 2 to 3
			for (I = 1; I <= 2; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[13]) minb[13] = tempw;
				if (tempw > maxb[13]) maxb[13] = tempw;
			}
			// ch 14 - 3 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[14] = tempw;
				maxb[14] = tempw;
			}
			else {
				if (tempw < minb[14]) minb[14] = tempw;
				if (tempw > maxb[14]) maxb[14] = tempw;
			}
			// get pix 2 to 3
			for (I = 1; I <= 2; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[14]) minb[14] = tempw;
				if (tempw > maxb[14]) maxb[14] = tempw;
			}
			// ch 15 - 3 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[15] = tempw;
				maxb[15] = tempw;
			}
			else {
				if (tempw < minb[15]) minb[15] = tempw;
				if (tempw > maxb[15]) maxb[15] = tempw;
			}
			// get pix 2 to 3
			for (I = 1; I <= 2; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[15]) minb[15] = tempw;
				if (tempw > maxb[15]) maxb[15] = tempw;
			}
			// ch 16 - 3 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[16] = tempw;
				maxb[16] = tempw;
			}
			else {
				if (tempw < minb[16]) minb[16] = tempw;
				if (tempw > maxb[16]) maxb[16] = tempw;
			}
			// get pix 2 to 3
			for (I = 1; I <= 2; I++) {
				tempw = Buf12[K];
				K++;
				if ((K > kmax) && ff ) break;
				if (tempw < minb[16]) minb[16] = tempw;
				if (tempw > maxb[16]) maxb[16] = tempw;
			}
			// ch 1 - 2 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[1] = tempw;
				maxb[1] = tempw;
			}
			else {
				if (tempw < minb[1]) minb[1] = tempw;
				if (tempw > maxb[1]) maxb[1] = tempw;
			}
			// get pix 2
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[1]) minb[1] = tempw;
			if (tempw > maxb[1]) maxb[1] = tempw;

			// ch 19 - 1 pixel
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[19] = tempw;
				maxb[19] = tempw;
			}
			else {
				if (tempw < minb[19]) minb[19] = tempw;
				if (tempw > maxb[19]) maxb[19] = tempw;
			}

			// ch 2 - 2 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[2] = tempw;
				maxb[2] = tempw;
			}
			else {
				if (tempw < minb[2]) minb[2] = tempw;
				if (tempw > maxb[2]) maxb[2] = tempw;
			}
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[2]) minb[2] = tempw;
			if (tempw > maxb[2]) maxb[2] = tempw;

			// ch 20 - 1 pixel
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[20] = tempw;
				maxb[20] = tempw;
			}
			else {
				if (tempw < minb[20]) minb[20] = tempw;
				if (tempw > maxb[20]) maxb[20] = tempw;
			}

			// ch 3 - 2 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[3] = tempw;
				maxb[3] = tempw;
			}
			else {
				if (tempw < minb[3]) minb[3] = tempw;
				if (tempw > maxb[3]) maxb[3] = tempw;
			}
			// get pix 2
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[3]) minb[3] = tempw;
			if (tempw > maxb[3]) maxb[3] = tempw;

			// ch 21 - 1 pixel
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[21] = tempw;
				maxb[21] = tempw;
			}
			else {
				if (tempw < minb[21]) minb[21] = tempw;
				if (tempw > maxb[21]) maxb[21] = tempw;
			}

			// ch 4 - 2 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[4] = tempw;
				maxb[4] = tempw;
			}
			else {
				if (tempw < minb[4]) minb[4] = tempw;
				if (tempw > maxb[4]) maxb[4] = tempw;
			}
			// get pix 2
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[4]) minb[4] = tempw;
			if (tempw > maxb[4]) maxb[4] = tempw;

			// ch 22 - 1 pixel
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[22] = tempw;
				maxb[22] = tempw;
			}
			else {
				if (tempw < minb[22]) minb[22] = tempw;
				if (tempw > maxb[22]) maxb[22] = tempw;
			}

			// ch 5 - 2 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[5] = tempw;
				maxb[5] = tempw;
			}
			else {
				if (tempw < minb[5]) minb[5] = tempw;
				if (tempw > maxb[5]) maxb[5] = tempw;
			}
			// get pix 2
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[5]) minb[5] = tempw;
			if (tempw > maxb[5]) maxb[5] = tempw;

			// ch 23 - 1 pixel
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[23] = tempw;
				maxb[23] = tempw;
			}
			else {
				if (tempw < minb[23]) minb[23] = tempw;
				if (tempw > maxb[23]) maxb[23] = tempw;
			}

			// ch 6 - 2 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				minb[6] = tempw;
				maxb[6] = tempw;
			}
			else {
				if (tempw < minb[6]) minb[6] = tempw;
				if (tempw > maxb[6]) maxb[6] = tempw;
			}
			// get pix 2
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[6]) minb[6] = tempw;
			if (tempw > maxb[6]) maxb[6] = tempw;

			// ch 24 - 1 pixel *
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[24] = maxb[24] = tempw;
			}
			else {
				if (tempw < minb[24]) minb[24] = tempw;
				if (tempw > maxb[24]) maxb[24] = tempw;
			}

			// ch 7 - 2 pixels
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (N == 1) {
				// get initial pix
				minb[7] = maxb[7] = tempw;
			}
			else {
				if (tempw < minb[7]) minb[7] = tempw;
				if (tempw > maxb[7]) maxb[7] = tempw;
			}

			// get pix 2
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[7]) minb[7] = tempw;
			if (tempw > maxb[7]) maxb[7] = tempw;

			// ch 24 - 1 pixel *
			tempw = Buf12[K];
			K++;
			if ((K > kmax) && ff ) break;
			if (tempw < minb[24]) minb[24] = tempw;
			if (tempw > maxb[24]) maxb[24] = tempw;
		}
	}

	for (I = 1; I <= 24; I++) {
		mintemp = maxb[I];
		mintemp += 12;
		if (mintemp > 3800) mintemp = 3800;
		maxb[I] = mintemp;
	}

	for (I = 1; I <= 24; I++) {
		mintemp = minb[I];
		mintemp -= 24;
		if (mintemp < 500) mintemp = 500;
		minb[I] = mintemp;
	}
}

void process_MIS(const char *file_name) {
	FILE *infile;
	int I, J, K, N;
	word tempw, tempw2;
	bool Sync2;

	infile = fopen(file_name, "rb+");
	if (!infile) {
		perror("Failed to open input file");
		return;
	}

	// Seek to position 910 words (assuming word = 2 bytes)
	if (fseek(infile, 910 * sizeof(word), SEEK_SET) != 0) {
		perror("Failed to seek in input file");
		fclose(infile);
		return;
	}

	for (I = 0; I < 900; I++) {
		Buf[I] = 0x0;
	}

	N = 0;
	for (J = 1; J <= 10; J++) {
		// Read 890 words in reverse order into Buf
		for (I = 889; I >= 0; I--) {
			word w;
			if (fread(&w, sizeof(word), 1, infile) != 1) {
				perror("Failed to read word");
				fclose(infile);
				return;
			}
			Buf[I] = w;
		}
		// Copy Buf to Bufdat sequentially
		for (I = 0; I <= 889; I++) {
			Bufdat[N] = Buf[I];
			N++;
		}
		// Read 10 words and discard
		for (K = 1; K <= 10; K++) {
			word discard;
			if (fread(&discard, sizeof(word), 1, infile) != 1) {
				perror("Failed to read discard word");
				fclose(infile);
				return;
			}
		}
	}
	fclose(infile);

	Sync2 = false;
	N = 0;
	K = 0;
	while (!Sync2 && (N < 8900)) {
		do {
			tempw = Bufdat[N] & 0x00FF;
			N++;
		} while ((tempw != 0x000F) && (N < 8900));
		tempw2 = Bufdat[N];
		if (tempw2 == 0x0F0F) Sync2 = true;
	}
	//printf("%d\n", Sync2); // prints 1
	// Load sync into Buf12
	Buf12[K++] = 0x00F0;
	Buf12[K++] = 0x0F0F;
	//printf("%d; %d\n", N, K);
	if (Sync2 && (N + 2250) < 9000) {  // 2250 = 750 * 3
		write12(&N, &K);
		scales(K - 1);
	}

	infile = fopen(file_name, "rb+");
	if (!infile) {
		perror("Failed to open input file for writing");
		return;
	}
	if (fseek(infile, 10 * sizeof(word), SEEK_SET) != 0) {
		perror("Failed to seek in input file for writing");
		fclose(infile);
		return;
	}

	// Write maxb and minb arrays
	for (I = 1; I < 25; I++) {
		write_little_endian_16(infile, maxb[I]);
	}
	//if (maxb[8] == 0x0ABF)
	//	printf("Hex value:%04x\n", maxb[8]);
	for (I = 1; I < 25; I++) {
		write_little_endian_16(infile, minb[I]);
	}
	fclose(infile);
}
################################################################
// functions.h
#ifndef FUNCTIONS_H
#define FUNCTIONS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>

typedef unsigned short word;
typedef unsigned char byte;

typedef word wordArray[5001];      // 0..5000
typedef byte byteray[4];           // 1..4
typedef word D3_Sens_Rec[1470];    // 1..1470
								   
FILE *infile;      // word_File
FILE *infileD3;    // D3_File
FILE *outfile;     // text file
FILE *outfile_mis; // word_file

int tempi;
word Tempw;
wordArray Buf;
D3_Sens_Rec D3_Buff;
word EphT1, EphT2; // Ephemeris Time
word Long1, Long2; // Longitude
word Lat1, Lat2;   // Latitude
word ETC1, ETC2;   // ETC
word Sync;
int SenSel3;
char mis_name[256];
char info_path[256], file_path[256], data_root[256], prep_path[256], ms_path[256];
double ETC_Begin, ETC_End, Header_ETC, ETC_1;
word End_Dat;

// Additional variables used in the code snippet
char DT_Str[64];
char line[512];
char sen_str[64];
char fname[256];
time_t MyTime;
FILE *logfile;
typedef FILE* Word_File;
typedef FILE* D3_File;
int I, N, J, K;
unsigned short Tempw;
unsigned short Buf12[3000];
unsigned short Bufdat[9000];
unsigned short maxb[25];
unsigned short minb[25];

void write12(int *N, int *K);
void scales(int kmax);
void process_MIS(const char *file_name);
void write_little_endian_16(FILE *fp, uint16_t value);
#endif
###############################################################
// main.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>
#include <stdint.h>
#include "functions.h"
#define MAX_PATH_LEN 512

void combine(char* destination, const char* path1, const char* path2)
{
	if (path1 == NULL && path2 == NULL) {
		strcpy(destination, "");;
	}
	else if (path2 == NULL || strlen(path2) == 0) {
		strcpy(destination, path1);
	}
	else if (path1 == NULL || strlen(path1) == 0) {
		strcpy(destination, path2);
	}
	else {
		char directory_separator[] = "/";
#ifdef WIN32
		directory_separator[0] = '\\';
#endif
		const char *last_char = path1;
		while (*last_char != '\0')
			last_char++;
		int append_directory_separator = 0;
		if (strcmp(last_char, directory_separator) != 0) {
			append_directory_separator = 1;
		}
		strcpy(destination, path1);
		if (append_directory_separator)
			strcat(destination, directory_separator);
		strcat(destination, path2);
	}
}
const char* ExtractFileName(const char *path) {
	const char *slash = strrchr(path, '/');
	if (!slash) slash = strrchr(path, '\\');
	return slash ? slash + 1 : path;
}

void open_file(const char *file_name) {
	infileD3 = fopen(file_name, "rb");
	if (!infileD3) {
		fprintf(stderr, "Error opening file %s\n", file_name);
		exit(EXIT_FAILURE);
	}
}

void ssmis(void) {
	int I, J;
	word Word1, Word2;
	word TempW;
	unsigned short  result;

	// write the header
	write_little_endian_16(outfile_mis, Sync);
	write_little_endian_16(outfile_mis, Sync);
	fwrite(&EphT1, sizeof(word), 1, outfile_mis);
	fwrite(&EphT2, sizeof(word), 1, outfile_mis);
	fwrite(&Long1, sizeof(word), 1, outfile_mis);
	fwrite(&Long2, sizeof(word), 1, outfile_mis);
	fwrite(&Lat1, sizeof(word), 1, outfile_mis);
	fwrite(&Lat2, sizeof(word), 1, outfile_mis);
	fwrite(&ETC1, sizeof(word), 1, outfile_mis);
	fwrite(&ETC2, sizeof(word), 1, outfile_mis);

	// write the L data
	J = 24;
	for (I = 0; I < 695; I++) {
		TempW = D3_Buff[J];
		fwrite(&TempW, sizeof(word), 1, outfile_mis);
		J++;
	}

	// Write L end and T first words
	TempW = D3_Buff[719]; // end L word
	result = (int)TempW;
	Word1 = result & 0x000F;
	J = 757;
	TempW = D3_Buff[J];
	J++;
	result = (int)TempW;
	Word2 = (result >> 4) & 0x0FF0;
	Word1 = Word1 + Word2;
	TempW = D3_Buff[J];
	J++;
	result = (int)TempW;
	Word2 = result << 12;
	Word1 = Word1 + Word2;
	Word1 = Word1 & 0xFFFF;
	write_little_endian_16(outfile_mis, Word1);

	for (I = 1; I <= 193; I++) {
		result = (int)TempW;
		Word1 = result >> 4;
		TempW = D3_Buff[J];
		J++;
		result = (int)TempW;
		Word2 = result << 12;
		Word1 = Word1 + Word2;
		write_little_endian_16(outfile_mis, Word1);
	}

	// last word
	result = (int)TempW;
	Word1 = (result >> 4) & 0x000F;
	write_little_endian_16(outfile_mis, Word1);
}

// Procedure header
void header(void) {
	unsigned long TempLW;

	Sync = 0xAE2F;
	EphT1 = D3_Buff[0];
	EphT2 = D3_Buff[1];
	Long1 = D3_Buff[2];
	Long2 = D3_Buff[3];
	Lat1 = D3_Buff[4];
	Lat2 = D3_Buff[5];
	ETC1 = D3_Buff[10];
	ETC2 = D3_Buff[11];

	// Calculate ETC
	TempLW = ((uint32_t)ETC2 << 16) + ETC1;
	Header_ETC = (double)TempLW / 1024.0;
}

void DateTimeToString(char *buffer, const char *format, time_t t) {
	struct tm *tm_info = localtime(&t);
	strftime(buffer, 64, "%Y-%m-%dT%H:%M:%S", tm_info);
}

char *ChangeFileExt(const char *filename, const char *new_ext) {
	static char buffer[256];
	strcpy(buffer, filename);
	char *dot = strrchr(buffer, '.');
	if (dot) {
		*dot = '\0';
	}
	strcat(buffer, new_ext);
	return buffer;
}

void Flush(FILE *f) {
	fflush(f);
}

int main(int argc, char *argv[]) {
	char file_name[256];
	char dir_name[512];
	const char* dest = "C:/Users/M26814/Downloads/misout";
	char full_path[MAX_PATH_LEN];

	if (argc < 2) {
		printf("Usage: %s <filename>\n", argv[0]);
		return 1; // Exit with an error code
	}
	if (argc == 3) {
		strncpy(dir_name, argv[2], sizeof(dir_name) - 1);
		dir_name[sizeof(dir_name) - 1] = '\0';
	}
	else 
	{
		strncpy(dir_name, dest, sizeof(dir_name) - 1);
		dir_name[sizeof(dir_name) - 1] = '\0';
	}
	size_t path_len = strlen(dir_name);
	int separator = (path_len > 0 && dir_name[path_len - 1] != '/');

	strncpy(file_name, argv[1], sizeof(file_name) - 1);
	file_name[sizeof(file_name) - 1] = '\0';
	//printf("The assigned filename is: %s\n", file_name);

	// Convert date/time to string
	MyTime = time(NULL);
	DateTimeToString(DT_Str, "c", MyTime);
	snprintf(line, sizeof(line), "%s - File : %s ", DT_Str, file_name);
	logfile = stdout;
	fprintf(logfile, "%s\n", line);

	strncpy(fname, ExtractFileName(file_name), sizeof(fname) - 1);
	fname[sizeof(fname) - 1] = '\0';

	//printf("file_name: %s\n", file_name);
	open_file(file_name);
	for (I = 0; I < 25; I++) {
		maxb[I] = 0x0ED8;
		minb[I] = 0x01F4;
	}
	SenSel3 = 0;

	if (SenSel3 == 0) {
		strncpy(mis_name, ChangeFileExt(file_name, ".MIS"), sizeof(mis_name) - 1);
		mis_name[sizeof(mis_name) - 1] = '\0';
		strncpy(mis_name, ExtractFileName(mis_name), sizeof(mis_name) - 1);
		mis_name[sizeof(mis_name) - 1] = '\0';

		// Assuming prep_path is set somewhere
		char temp_path[512];
		snprintf(temp_path, sizeof(temp_path), "%s%s", prep_path, mis_name);
		strncpy(mis_name, temp_path, sizeof(mis_name) - 1);
		mis_name[sizeof(mis_name) - 1] = '\0';

		// Use snprintf to safely combine the strings
		if (separator) {
			snprintf(full_path, MAX_PATH_LEN, "%s/%s", dir_name, mis_name);  //linux
			// snprintf(full_path, MAX_PATH_LEN, "%s\\%s", dir_name, mis_name); //pc
		}
		else {
			snprintf(full_path, MAX_PATH_LEN, "%s%s", dir_name, mis_name);
		}

		//printf("Combined path: %s\n", full_path);
		//printf("test!\n");
		//printf("mis_name: %s\n", full_path);
		outfile_mis = fopen(full_path, "wb");
		if (!outfile_mis) {
			fprintf(stderr, "Error opening output file %s\n", full_path);
			exit(EXIT_FAILURE);
		}

		Sync = 0xAE2F;
		write_little_endian_16(outfile_mis, Sync);
		write_little_endian_16(outfile_mis, Sync);

		tempi = 0;
		for (I = 3; I <= 900; I++) {
			write_little_endian_16(outfile_mis, tempi);
		}
	}

	if (!infileD3) {
		fprintf(stderr, "Input file not opened\n");
		exit(EXIT_FAILURE);
	}

	// Read first D3_Buff
	if (fread(D3_Buff, sizeof(word), 1470, infileD3) != 1470) {
	}

	while (!feof(infileD3)) {
		for (N = 0; N < 1470; N++) {
			D3_Buff[N] = 0;
		}
		if (fread(D3_Buff, sizeof(word), 1470, infileD3) != 1470) {
			break; // EOF or error
		}
		header();
		ssmis();
	}

	fclose(infileD3);
	End_Dat = 0xFF00;
	if (SenSel3 == 0) {
		for (I = 1; I <= 900; I++) {
			write_little_endian_16(outfile_mis, End_Dat);
		}
		fclose(outfile_mis);
		process_MIS(full_path);
	}
	fprintf(logfile, "%s\n", line);
	Flush(logfile);

	return 0;
}
##################################################################
#Makefile
# Define the executable name and source files
TARGET = mstest
SOURCES = main.c functions.c
OBJECTS = $(SOURCES:.c=.o)  # Automatically create a list of object files

# Define compiler and flags
CC = gcc
CFLAGS = -Wall -Werror -g -std=c99

# The default rule (first rule in the file)
$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) $(OBJECTS) -o $(TARGET)

# Rule for compiling .c files into .o files
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Phony target to clean up generated files
.PHONY: clean
clean:
	rm -f $(TARGET) $(OBJECTS)

#############################################################
#mswatch_pctest.py
import os
import time 
import taskRsdr as schr
import sys
import datetime
import argparse

###watchDogDir = [r'\\Sd78mda02.northgrum.com\tgroups\B\Block-5\Data\PrepGen Processing\.MS Files of the day\2025\Dec\2025.12.09\F1614253.MS']  #wk 
### watchDogDir = [r'\\Sd78mda02.northgrum.com\tgroups\B\Block-5\Data\PrepGen Processing\.MS Files of the day\2025\'] ###wk
watchDogDir = [r'C:/Users/M26814/Downloads/misout/'] ###wk
#####watchDogDir = ['/scratch/users/m26814/newrawfiles/']
###destDir = '/mnt/scratch/2/dmsp/dmspdata/Processed/MIS-DropBox/December/testonly/' #destination for output files
##destDir = r'\\159.4.50.205\m26814\home\rain\scratch\dmsp\dmspdata\Processed\MIS-DropBox\December\testonly'
##destDir = r'\\159.4.50.205\dmsp\dmspdata\Processed\MIS-DropBox\December\testonly'
#destination for output files
###destDir = r'C:/Users/M26814/Downloads/msfiles/'
destDir = r'C:/tmp/testmsfiles/'
destination_folder = r'\\159.4.50.205\m26814\home\rain\m26814\test\tt\testonly'


### destDir = r'\\159.4.50.205\m26814\home\rain\m26814\test\tt\testonly'
##destDir = r'\\159.4.50.205/m26814/home/rain/m26814/test/tt/testonly'


#timeINT = 120 #interval time (seconds)
timeINT = 30 #interval time (seconds)
start_date = datetime.datetime.now()

date_format = '%Y%m%d' #folder name format

def find_files(directory, file_extension=None):
    found_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(file_extension.upper()) or file.endswith(file_extension.lower()):
                create_time = os.stat(os.path.join(root, file)).st_ctime
                if (start_date <= datetime.datetime.fromtimestamp(create_time)):
                   found_files.append(os.path.join(root, file))                   
    return found_files

def add_to_path(base_path, subdir_name):
    combined_path = os.path.join(base_path, subdir_name)
    return combined_path

#return a list of folders for monitoring
def folderList(dir):
    retList = []
    dlist = [d for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]
    for dd in dlist:
       create_time = os.stat(dir+"/"+dd).st_ctime
       if (start_date <= datetime.datetime.fromtimestamp(create_time)):
         retList.append(dd)

    return retList

#find and list dmsp files
def dmspFileList(subDir, j): 
    onlyfiles = []  
    listFiles = []  
    for i in range(len(subDir)):
      onlyfiles = [os.path.join(watchDogDir[j] + subDir[i], f) for f in os.listdir(watchDogDir[j] + subDir[i]) if os.path.isfile(os.path.join(watchDogDir[j] + subDir[i], f))]
      listFiles = listFiles + onlyfiles

    return(listFiles)

#search dmsp data files
def checkNewDmspFile(processedDmspFiles, newDmspFileList):
    differencesList = [x for x in newDmspFileList if x not in processedDmspFiles]
    return(differencesList)

#process dmsp data files
def processNewDmspdata(newDmspFiles):
    for i in newDmspFiles:
       create_time = os.stat(i).st_mtime
       print(i)
       if start_date <= datetime.datetime.fromtimestamp(create_time):
          schr.schTasks(i, destDir, watchDogDir, destination_folder)

#watchdog for new dmsp data files
def dmspDataWatcher(watchDir, timeINT):
    length = len(watchDir)
    processedDmspFiles = []
    startRunning = []
    newDmspFileList = []
    Diffs = []
    listDir = []
    for i in range(length):
       processedDmspFiles.append(0)
       startRunning.append(0)
       newDmspFileList.append(0)
       Diffs.append(0)
       listDir.append(0)

    while True:
       # Iterating the index
       for i in range(length):
           #starting running only
           if startRunning[i] == 0:
               processedDmspFiles[i] = []
               startRunning[i] = 1
           newDmspFileList[i] = find_files(watchDogDir[i], '.MS')                                     	   
           Diffs[i] = checkNewDmspFile(processedDmspFiles[i], newDmspFileList[i])

           processedDmspFiles[i] = newDmspFileList[i]
           if len(Diffs[i]) == 0:
              continue
           processNewDmspdata(Diffs[i])
       time.sleep(timeINT)

#driver code
if __name__ == "__main__":
#main function to launch a watchdog for the upcoming new dmsp data
#Usage: python3 {sys.argv[0]} <start_date_time (example: "11/30/23 15:31:26")>

   dateformat = "%m/%d/%y"
   timeformat = ("%H:%M:%S")   
   parser=argparse.ArgumentParser(description="argument parser")
   parser.add_argument("date_time", nargs='?',default="now",)
   args, unknown = parser.parse_known_args()
   
   isExist = os.path.exists(destDir)
   if not isExist:
      os.makedirs(destDir)

   if args.date_time=="now":
       print(start_date)
   else:           
          dt_str = args.date_time       
          test_str = (dt_str.strip()).split()
          if len(test_str) == 2:
             try:
                 validstr = bool(datetime.datetime.strptime(test_str[0], dateformat))
                 validstr = bool(datetime.datetime.strptime(test_str[1], timeformat))
             except ValueError:
                 validstr = False
                 print('Usage: python3 dmspWatch.py "start_date_time"(example: "11/30/23 15:31:26")')
                 sys.exit()
          else:   
             print('Usage: python3 dmspWatch.py "start_date_time"(example: "11/30/23 15:31:26")')
             sys.exit()

          datetime_object = datetime.datetime.strptime(dt_str, '%m/%d/%y %H:%M:%S')
          start_date = datetime_object
          print(start_date)
   dmspDataWatcher(watchDogDir, timeINT)

   sys.exit()

#####################################################
#msFile.py
import subprocess
import os
import sys
import glob
import re
import shutil
import shlex
from pathlib import Path
import time 
import datetime

month_dict = {'01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', 
             '06': 'Jun', '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', 
             '11': 'Nov', '12': 'Dec'}
newtest = True

def srcfile2ext(file_path):
    base_name, extension = os.path.splitext(file_path)
    new_extension = extension.lower()
    new_file_path = base_name + new_extension
    try:
        os.rename(file_path, new_file_path)
    except:
        print(f"error in file: {file_path}")
        
def findfiles(path, pat, keys):
    nofile = "skip"
    matchfiles = os.path.join(path, pat)
    pp = glob.glob(matchfiles)
    for index, item in enumerate(pp):
        ff = os.path.basename(pp[index])
        ll = getnums(ff)
        if (keys > ll[0]) and (keys < ll[1]):
            return ff
    return nofile
    
def find_folder(root_path, folder_name):
    root = Path(root_path)
    matches = [path for path in root.rglob(folder_name) if path.is_dir()]
    return matches
    
def find_or_create_folder(base_path, folder_name):
    for root, dirs, files in os.walk(base_path):
        if folder_name in dirs:
            return os.path.join(root, folder_name)
    
    new_path = os.path.join(base_path, folder_name)
    os.makedirs(new_path, exist_ok=True)
    return new_path


def get_subpath(full_path, base_path):
    try:
        relative_path = os.path.relpath(full_path, base_path)
        return relative_path
    except ValueError:
        return full_path

def getnums(string):
     return [int(x) for x in re.findall(r'\d+', string)]

#dmsp data
def rsdrprocess(src, dest, indir, datadir):
    print(src, dest, indir, datadir)
    basename = os.path.basename(src)
    if basename.find('ms') != -1 or basename.find('MS') != -1:#lc test
       if newtest:
          create_time = os.stat(src).st_mtime
          stimestamp = datetime.datetime.fromtimestamp(create_time)
          syear = stimestamp.year
          smonth = f"{stimestamp.month:02d}"
          sday = f"{stimestamp.day:02d}"
          sdatafolder = str(syear)+"."+str(smonth)+"."+str(sday)
          ndest = os.path.join(dest, str(syear), str(month_dict[smonth]), sdatafolder)
          print("ntest", ndest)
          dest = ndest
          Path(ndest).mkdir(parents=True, exist_ok=True)
       else:
          subpath = get_subpath(src, indir[0])
          subpath = os.path.dirname(subpath) + "/"
          if basename.find('ms') != -1 or basename.find('MS') != -1:
             subpath = subpath.lstrip('/')
             subpath = subpath.lstrip('\\')
             if subpath != '/' and subpath != '':
                dest = os.path.join(dest, subpath.lstrip('/'))
                ddest = (dest.rstrip('/')).rsplit('/', 1)[0]   
                if not newtest:
                   dest = ddest + "/" + datadir
             isExist = os.path.exists(dest)
             if not isExist:
                os.makedirs(dest)
       base, ext = os.path.splitext(basename) 
       src_file = shlex.quote(src)
       cmd = "mstest " + src_file + " " + str(dest).rstrip('/')            
       os.system(cmd) 
       print("end")
            
#driver of rsdr processing
if __name__ == '__main__':
    if len(sys.argv) > 2 : 
       rsdrprocess(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    else:
       raise SystemExit(f"Usage: python3 {sys.argv[0]} <dmsp_data> <output_path> <indir_path>...")  

##################################################################
#mswatch.py
import os
import time 
import mstaskRsdr as schr
import sys
import datetime
import argparse
from pathlib import Path

test_flag = False
test_folder = "/2026/testonlyms/"
if test_flag:
   watchDogDir = ['/mnt/prep' + test_folder]
   watchDogBaseDir = ['/mnt/prep']
   
   destDir = '/mnt/scratch/2/dmsp/dmspdata/Processed/MIS-DropBox/'
else:
   watchDogDir = ['/mnt/prep/2026']
   destDir = '/mnt/scratch/2/dmsp/dmspdata/Processed/MIS-DropBox/'

timeINT = 30
start_date = datetime.datetime.now()
timeout=10

fileList = False
file_list = []
##new_files = False from a special date
new_files = True
date_format = '%Y%m%d'

def find_files(directory, file_extension=None):
    found_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(file_extension.upper()) or file.endswith(file_extension.lower()):
                try:
                   create_time = os.stat(os.path.join(root, file)).st_mtime	
                except FileNotFoundError:
                   print(f"Error: The file '{file_path}' does not exist. Skipping...")
                   return "-1"
                except PermissionError:
                   print(f"Error: Permission denied to access '{file_path}'. Skipping...")
                   return "-1"
                except Exception as e:
                   print(f"An unexpected error occurred: {e}")		   
                   return "-1"

                if test_flag or new_files:
                   if fileList:
                      if file in file_list:
                         found_files.append(os.path.join(root, file))
                   else:
                      found_files.append(os.path.join(root, file))
                else:
                   if (start_date <= datetime.datetime.fromtimestamp(create_time)):
                      found_files.append(os.path.join(root, file))
                 
    return found_files
	
def file_exists_recursive(target_filename, search_dir):
    for root, dirs, files in os.walk(search_dir):
        if target_filename in files:
            return os.path.join(root, target_filename)
    return None
	
def wait_until_ready(file_path):
	start_time = time.time()
	last_size = -1
	while time.time() - start_time < timeout:
		try:
			current_size = os.path.getsize(file_path)
			if current_size == last_size and current_size > 0:
				return True
			last_size = current_size
		except OSError:
			pass
		time.sleep(1)
	print(f"Timed out waiting for file: {file_path}")
	return False

def add_to_path(base_path, subdir_name):
    combined_path = os.path.join(base_path, subdir_name)
    return combined_path

#search dmsp data files
def checkNewDmspFile(processedDmspFiles, newDmspFileList):
    differencesList = [x for x in newDmspFileList if x not in processedDmspFiles]
    return(differencesList)

#process dmsp data files
def processNewDmspdata(newDmspFiles):
    for i in newDmspFiles:	
       if not os.path.isfile(i):
          if wait_until_ready(i):
             print(i)
          else:
             continue

       srcfile = Path(i).name
       if srcfile.find('ms') != -1 or srcfile.find('MS') != -1:
          ifile = Path(i)
          new_path = ifile.with_suffix(".MIS")
          new_path = Path(new_path).name
          found_path = file_exists_recursive(new_path, destDir.rstrip("/"))
          if found_path:
             print("with file:", i)
             continue

       create_time = os.stat(i).st_mtime		
       stimestamp = datetime.datetime.fromtimestamp(create_time)
       syear = stimestamp.year
       smonth = f"{stimestamp.month:02d}"
       sday = f"{stimestamp.day:02d}"
       sdatafolder = str(syear)+"."+str(smonth)+"."+str(sday)  
       
       if test_flag:
          schr.schTasks(i, destDir, watchDogBaseDir, sdatafolder)
       else:
          schr.schTasks(i, destDir, watchDogDir, sdatafolder)

#watchdog for new dmsp data files
def dmspDataWatcher(watchDir, timeINT):
    length = len(watchDir)
    processedDmspFiles = []
    startRunning = []
    newDmspFileList = []
    Diffs = []
    listDir = []
    for i in range(length):
       processedDmspFiles.append(0)
       startRunning.append(0)
       newDmspFileList.append(0)
       Diffs.append(0)
       listDir.append(0)

    while True:
       # Iterating the index
       for i in range(length):
           #starting running only
           if startRunning[i] == 0:
               processedDmspFiles[i] = []
               startRunning[i] = 1
               if new_files:
                  print("new")
                  processedDmspFiles[i] = find_files(watchDogDir[i], '.MS')

           gfiles = find_files(watchDogDir[i], '.MS') 
           if gfiles == "-1":
              print("error and wait")
           else:
              newDmspFileList[i] = gfiles	   
              Diffs[i] = checkNewDmspFile(processedDmspFiles[i], newDmspFileList[i])
              processedDmspFiles[i] = newDmspFileList[i]
              if len(Diffs[i]) == 0:
                 continue
              processNewDmspdata(Diffs[i])
	   
       time.sleep(timeINT)

#driver code
if __name__ == "__main__":
#main function to launch a watchdog for the upcoming new dmsp data
#Usage: python3 {sys.argv[0]} <start_date_time (example: "11/30/23 15:31:26")>
   # global start_date
   # global new_files
   dateformat = "%m/%d/%y"
   timeformat = ("%H:%M:%S")   
   parser=argparse.ArgumentParser(description="argument parser")
   parser.add_argument("date_time", nargs='?',default="now",)
   args, unknown = parser.parse_known_args()

   isExist = os.path.exists(destDir)
   if not isExist:
      os.makedirs(destDir)

   if args.date_time=="now":
       if not test_flag:
          new_files = True
          print("now: ", start_date, "new files")
       else:
          new_files = False
          print("now: ", start_date)

   else:
       dt_str = args.date_time
       new_files = False       
       test_str = (dt_str.strip()).split()
       if len(test_str) == 2:
          try:
             validstr = bool(datetime.datetime.strptime(test_str[0], dateformat))
             validstr = bool(datetime.datetime.strptime(test_str[1], timeformat))
          except ValueError:
             validstr = False
             print('Usage: python3 dmspWatch.py "start_date_time" \
                   (example: "11/30/23 15:31:26")')
             sys.exit()
       else:   
          print('Usage: python3 dmspWatch.py "start_date_time" \
               (example: "11/30/23 15:31:26")')
          sys.exit()

       datetime_object = datetime.datetime.strptime(dt_str, '%m/%d/%y %H:%M:%S')
       start_date = datetime_object
       print(start_date)
   dmspDataWatcher(watchDogDir, timeINT)

   sys.exit()

#######################################################
#mstaskRsdr.py
import subprocess
import os
import sys
import msFile

#schedule a task
def schTasks(src, dest, indir, sdataDir):
    msFile.rsdrprocess(src, dest, indir, sdataDir)

#driver
if __name__ == '__main__':
    print("test", sys.argc)
    if len(sys.argc) > 2 : 
       schTasks(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    else:
       raise SystemExit(f"Usage: python3 {sys.argv[0]} \
             <dmsp_data> <output_path> <indir_path> <sdir_path>...")
			 
######################################################
#taskScheduler.py
import subprocess
import os
import sys

#schedule and run the tasks
def schTasks(src, dest, indir):
    cmd = "python3 ./dmspProcessing.py " + src + " " + dest + " " + indir[0]
    process = subprocess.Popen(cmd, shell=True, executable='/bin/bash', \
                               stdout=subprocess.PIPE)
    proc_output, proc_error = process.communicate()
    
    for line in proc_output.decode('utf8').split("\n"):
       print( line )


#driver of scheduler
if __name__ == '__main__':

    if len(sys.argv) > 2 : 
       schTasks(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
       raise SystemExit(f"Usage: python3 {sys.argv[0]} <dmsp_data> \
                         <output_path> <indir_path>...")
##################################################
#rsdrMonitor.py
import os
import time 
import taskScheduler as schr
import sys
import datetime
import argparse
import fnmatch
 
test_flag = False ##True: for test only
test_folder = "/2026/testonly/"
if test_flag:
   watchDogDir = ['/scratch/users/m26814/newrsdrfiles/' + test_folder]
   destDir = '/scratch/users/m26814/newoutput/' + test_folder
else:
   watchDogDir = ['/scratch/users/m26814/newrsdrfiles/']
   destDir = '/scratch/users/m26814/newoutput/'


timeINT = 40 #interval time (seconds)
start_date = datetime.datetime.now()
timeout=30

fileList = False
file_list = ['F16_14981.dat', 'F16_14980.dat', 'F17_99273.dat', \
             'F17_99274.dat', 'F18_83991.dat', 'F18_83992.dat']

date_format = '%Y%m%d'

def find_files(directory, file_extension = None):
    found_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(file_extension.upper()) or file.endswith(file_extension.lower()):
                create_time = os.stat(os.path.join(root, file)).st_mtime
                if test_flag:
                   if fileList:
                      if file in file_list:
                         found_files.append(os.path.join(root, file))
                   else:
                      found_files.append(os.path.join(root, file))
                else:
                   if (start_date <= datetime.datetime.fromtimestamp(create_time)):
                      found_files.append(os.path.join(root, file))
					  
    return found_files
	
def wait_until_ready(file_path):
	start_time = time.time()
	last_size = -1
	while time.time() - start_time < timeout:
		try:
			current_size = os.path.getsize(file_path)
			if current_size == last_size and current_size > 0:
				return True
			last_size = current_size
		except OSError:
			pass
		time.sleep(1)
	print(f"Timed out waiting for file: {file_path}")
	return False
	
def add_to_path(base_path, subdir_name):
    combined_path = os.path.join(base_path, subdir_name)
    return combined_path

#find and list dmsp files
def dmspFileList(subDir, j): 
    onlyfiles = []  
    listFiles = []  
    for i in range(len(subDir)):
      onlyfiles = [os.path.join(watchDogDir[j] + subDir[i], f) 
                for f in os.listdir(watchDogDir[j] + subDir[i]) \
                if os.path.isfile(os.path.join(watchDogDir[j] + subDir[i], f))]
      listFiles = listFiles + onlyfiles

    return(listFiles)

#search new dmsp data files
def checkNewDmspFile(processedDmspFiles, newDmspFileList):
    differencesList = [x for x in newDmspFileList if x not in processedDmspFiles]
    return(differencesList)

#process new dmsp data files
def processNewDmspdata(newDmspFiles):
    for i in newDmspFiles:
       if not os.path.isfile(i):
          if wait_until_ready(i):
             print(i)
          else:
             continue
       schr.schTasks(i, destDir, watchDogDir)

#watchdog for new dmsp data files
def dmspDataWatcher(watchDir, timeINT):
    length = len(watchDir)
    processedDmspFiles = []
    startRunning = []
    newDmspFileList = []
    Diffs = []
    listDir = []
    for i in range(length):
       processedDmspFiles.append(0)
       startRunning.append(0)
       newDmspFileList.append(0)
       Diffs.append(0)
       listDir.append(0)

    while True:
       # Iterating the index
       for i in range(length):
           #starting running only
           if startRunning[i] == 0:
               processedDmspFiles[i] = []
               startRunning[i] = 1
           newDmspFileList[i] = find_files(watchDogDir[i], '.dat')
           Diffs[i] = checkNewDmspFile(processedDmspFiles[i], newDmspFileList[i])
           processedDmspFiles[i] = newDmspFileList[i]
           if len(Diffs[i]) == 0:
              continue
           processNewDmspdata(Diffs[i])
       if test_flag:
           sys.exit()
       else:
           time.sleep(timeINT)

#driver code
if __name__ == "__main__":
#main function to launch a watchdog for the upcoming new dmsp data
#Usage: python3 {sys.argv[0]} <start_date_time (example: "11/30/23 15:31:26")>
   # global start_date
   dateformat = "%m/%d/%y"
   timeformat = ("%H:%M:%S") 

   
   parser=argparse.ArgumentParser(description="argument parser")
   parser.add_argument("date_time", nargs='?',default="now",)
   args, unknown = parser.parse_known_args()
   
   if args.date_time=="now":
       print("now:", start_date)
   else:           
       dt_str = args.date_time       
       test_str = (dt_str.strip()).split()
       if len(test_str) == 2:
          try:
             validstr = bool(datetime.datetime.strptime(test_str[0], dateformat))
             validstr = bool(datetime.datetime.strptime(test_str[1], timeformat))
          except ValueError:
             validstr = False
             print('Usage: python3 rsdrMonitor.py "start_date_time" \
                  (example: "11/30/23 15:31:26")')
             sys.exit()
       else:   
          print('Usage: python3 rsdrMonitor.py "start_date_time" \
               (example: "11/30/23 15:31:26")')
          sys.exit()

       datetime_object = datetime.datetime.strptime(dt_str, '%m/%d/%y %H:%M:%S')
       start_date = datetime_object
       print(start_date)
   dmspDataWatcher(watchDogDir, timeINT)

   sys.exit()
#####################################################
#dmspProcessing.py
import subprocess
import os
import sys
import glob

def get_subpath(full_path, base_path):
    try:
        relative_path = os.path.relpath(full_path, base_path)
        return relative_path
    except ValueError:
        return full_path

#process the new dmsp data
def process(src, dest, indir):
    args = os.path.basename(src)
    pp = get_subpath(src, indir)
    pp = os.path.dirname(pp) + "/"

    if args.lower().find('dat') != -1:
       if pp != '/':
          print(pp)
          dest = os.path.join(dest, pp)

       isExist = os.path.exists(dest)
       if not isExist:
         os.makedirs(dest)

       revNum = (args.split('_', 1)[1]).split('.')[0]
       satNum = (args.split('_')[0])[1:3]     
       cmd = "processing_sdrp " + satNum + " " + revNum + " " + revNum + " " + dest
       print(subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, \
             encoding='utf-8').communicate()[0])
       #clean up unused files
       files = glob.glob(dest + 'TDR_*.DIAG')
       files.extend(glob.glob(dest + 'SDR_*.DIAG'))
       files.extend(glob.glob(dest + 'ENVs_*.DIAG'))
       
       for f in files:
           try:
               os.remove(f)
           except OSError as e:
               print("Error: %s : %s" % (f, e.strerror))

#driver of processing
if __name__ == '__main__':
    if len(sys.argv) > 2 : 
       process(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
       raise SystemExit(f"Usage: python3 {sys.argv[0]} \
                        <dmsp_data> <output_path> <indir_path>...")

##########################################################
#!/usr/bin/perl
#
#------------------------------------------------------------------------
# Run the Sensor Data Record Processor on multiple machines in parallel.
#------------------------------------------------------------------------
#processing_sdrp

use English;	# enable understandable long names for builtin perl variables
use strict;	# strict variable checking
use Time::HiRes qw(time);
use Sys::Hostname;
use Time::Local;

$OUTPUT_AUTOFLUSH = 1;

####################
# GLOBAL CONSTANTS #
####################
use constant SDRP_FATAL => 1;		# Must be the same as STOP 1 in FORTRAN
use constant SDRP_IDL_FATAL => 2;	# IDL GPS caught exception (bad data etc)
use constant SDRP_IDL_ERROR => 3;	# IDL error - equivalent to FORTRAN crash
use constant SDRP_NORUN => -1;		# SDRP didn't even run
use constant SDRP_CRASH => -2;		# SDRP ran but crashed
use constant SSH_ERROR  => -3;		# Connection/ssh error

use constant BYTES_PER_SCAN => 4700;	# Average bytes of RSDR per SSMIS scan
use constant GZIP_COMPRESSION => 0.72;	# Average compression ratio for gzipped
					# RSDR files

use constant TMP_DIR	   => '/home/data/dmsp/sdrp';	# Temp/scratch dir
use constant LOCAL_TMP_DIR => '/data/dmsp/sdrp';	# Local temp/scratch dir

####################
# GLOBAL VARIABLES #
####################

my %default_linuxes = (	# List of default Linux machines to use.  The numbers
			# determine the sort order when starting out.  They
			# don't have to be unique.
    rain	=> 1,
    typhoon	=> 1,
);

my %num_processors = (	# Number of processors to use on each machine.  If not
    rain	=> 8,	# listed here, assume 1.
    typhoon	=> 8,
);

my %common_hostname = (	# When determining the local hostname, wind/vector
			# will return adevwh01/adevwh02 instead of wind/vector.
			# This maps from one to the other.
    'ssmis-rhwks01.northgrum.com'    =>'rain',
    'ssmis-rhwks02.northgrum.com'    =>'typhoon',

);


my @linuxes;		# Working list of Linux machines: combination of defaults
			# and user-specified.
my $local_only = 1;	# True (1) if we should only use the local machine
			# (don't farm out jobs to networked machines).
			#
my %local;		# KEY:   a machine name.
			# VALUE: true if the machine is this machine; we bypass
			#        ssh for this machine and just run directly.
			#
my @revlist;		# List of rev numbers requested to run.
my @main_args;		# Primary command-line arguments: flight number, start
			# rev, stop rev, output dir.
my @sdrp_crash_rsdrs;	# List of RSDR files that got SDRP fatal errors.
my @sdrp_fatal_rsdrs;	# List of RSDR files that crashed SDRP.
my @revrsdr;		# List of RSDR files to run in the current iteration.


my %busy;		# KEY:   a machine name.
			# VALUE: number of processors in use, or
			#        system time value after which the machine will
			#        be considered available again.

my %pids;		# KEY:   pid of a child process.
			# VALUE: the machine being used to run this process.

my %file;		# KEY:   pid of a child process.
			# VALUE: the RSDR file being run by this process.

my %revs;		# KEY:   pid of a child process.
			# Value: unique rev number being run by this process.

my %run;		# KEY:   pid of a child process.
			# Value: the run script file being used by this process.

my %rev_processed;	# KEY:   unique rev number.
			# Value: true (1) if this rev is being (or has been)
			#        processed.

my %retry_rsdr;		# KEY:   name of an RSDR file that needs to be retried
			#        because the machine running it must have failed.
			# VALUE: unused.

my %starttime;		# KEY:   a process ID (PID).
			# VALUE: timestamp of script start for that child PID.

my %runtime;		# KEY:   a machine name.
			# VALUE: total run time of all revs on that machine.

my %runs;		# KEY:   a machine name.
			# VALUE: total number of SDRP runs on that machine.

my %crash;		# KEY:   a machine name.
			# VALUE: number of crashes for this machine since the
			#        last good run.

my %core_file;		# KEY:   name of an RSDR file that crashed SDRP
			# VALUE: name of the corresponding core file

my %status_file;	# KEY:   a process ID (PID) or name of an RSDR file
			#        that crashed SDRP
			# VALUE: the output/status file from this process

my $sdrp;		# Path to SDRP executable.
my $fltnum;		# Flight number (user-specified).
my $start;		# Start rev (user-specified).
my $stop;		# Stop rev (user-specified).
my $destdir;		# Output directory (user-specified or GPS_ODIR).
my $sat = 1;		# Satellite number.
my $const = 1;		# Constants file number.
my $finished = 0;	# True if we should finish now (user-interrupted).

my $wait_after_failure = 900;	# Default time to remove a machine from the pool
				# after it fails to run a particular rev.
				# Maybe it's just temporarily down, so we don't
				# want to remove it permanently from the pool.

my $nextrev = 1;	# Number of revs to the next rev when moving forward.
			# Default of 1 means process every rev (go 1 forward
			# each time).

my $keep_files = 0;	# True (1) if we should keep generated script files
			# and exit status output files

my $min_rsdr_size = 0;	# Minimum file size to run an RSDR file.  If positive,
			# files below this size will be skipped.

##############
# BEGIN CODE #
##############

my $script_start = time;

#
# Get command line arguments.
#
my $arg = shift;
while (defined($arg)) {
  # Add a machine to the list.
  if ($arg eq '-a') {
    my $add = lc shift;
    if (defined($add)) {
      push(@linuxes, $add);
    }
  }

  # Exclude a machine from the default list.
  elsif ($arg eq '-x') {
    my $exclude = lc shift;
    if (defined($exclude)) {
      delete $default_linuxes{$exclude};
    }
  }

  # Wait before adding a failed machine back to the list.
  elsif ($arg eq '-w') {
    my $wait = (shift) + 0;
    if ($wait > 0) {
      $wait_after_failure = $wait;
    }
  }

  # Run every 'j' revs
  elsif ($arg eq '-j') {
    $nextrev = (shift) + 0;
    if ($nextrev < 1) {
      $nextrev = 1;
    }
  }

  # Keep intermediate (script/status) files.
  elsif ($arg eq '-k') {
    $keep_files = 1;
  }

  # Minimum approximate scans to run an RSDR file.
  elsif ($arg eq '-s') {
    $min_rsdr_size = ((shift) + 0) * BYTES_PER_SCAN;
  }

  # Use networked machines in addition to local.
  elsif ($arg eq '-n') {
    $local_only = 0;
  }

  # This must be one of the primary four arguments.  Save it for below.
  else {
    push(@main_args, $arg);
  }

  $arg = shift;
}

#
# Get main arguments in order.
#
$fltnum = shift(@main_args);
$start = shift(@main_args);
$stop = shift(@main_args);
$destdir = shift(@main_args);

#
# Make sure the num_processors list matches the default_linuxes list.
# Add any that aren't listed, assuming just 1 processor for those.
#
my $hostname = Sys::Hostname::hostname();
if (defined($common_hostname{$hostname})) {
    $hostname = $common_hostname{$hostname};
}
foreach my $linux (keys %default_linuxes) {
  unless (defined($num_processors{$linux})) {
    $num_processors{$linux} = 1;
  }
  # If the name matches our hostname, this is the local machine.
  # Use this info later to bypass the ssh connection, and just run directly.
  if ($linux =~ /^$hostname$/io) {
    $local{$linux} = 1;
  } elsif ($local_only) {
    delete $default_linuxes{$linux};
  }
}

#
# Add default machines to the working list.  User-added machines will be ahead of them.
#
push(@linuxes, sort { $default_linuxes{$a} <=> $default_linuxes{$b} } keys %default_linuxes);

#
# Check flight number, start and stop rev numbers.
#
unless (defined($fltnum) && defined($start) && defined($stop)) {
  die &usage();
}

my @env_dirs = (
  'GPS_DFDIR',
  'GPS_DBDIR',
  'GPS_EXEDIR',
);

#
# If we're farming jobs to networked machines, the environment paths ought
# to be /home/... and not local.  Check if we're in /Users/... and convert
# that to /home/hostname/...
#

unless ($local_only) {
  my $home_dir = "/home/$hostname";
  my $home_data = (-l '/home/data') ? '/home/data' : '/home/data2';
  
  foreach my $dir (@env_dirs) {
    if ($ENV{$dir} =~ /^\/Users\// && -d $home_dir) {
      $ENV{$dir} =~ s/^\/Users/$home_dir/o;
    } elsif ($ENV{$dir} =~ /^\/data\// && -l $home_data) {
      $ENV{$dir} =~ s/^\/data/$home_data/o;
    }
  }
}
foreach my $dir (@env_dirs) { print "$dir=$ENV{$dir}\n"; }

#
# Check that environment is properly setup.
#
foreach my $dir (@env_dirs) {
  unless (-d $ENV{$dir}) {
    die "Please source gps_setdir ($dir '$ENV{$dir}' is not a dir).\n";
  }
}
my $sdrp_exe = $ENV{SDRP_EXE} || 'sdrp';
$sdrp = "$ENV{GPS_EXEDIR}$sdrp_exe";
die "Can't find sdrp or is not executable ('$sdrp')\n" unless (-x $sdrp);

#
# Check destination directory: default if not set is $GPS_ODIR.
#
if (!defined($destdir)) {
  $destdir = $ENV{GPS_ODIR};
}
if ((! -d $destdir) || (! -w $destdir)) {
  die "Destination '$destdir' is not a directory or not writable.\n" . &usage();
}

#
# If any machines don't respond, consider them eternally busy.
#
for my $sun (@linuxes) {
  print "Checking $sun... ";
  $busy{$sun} = &check_dead_sun($sun);
  if ($busy{$sun}) {
    print "offline, not using.\n";
    $busy{$sun} = time + $wait_after_failure;
  } else {
    print "ok.\n";
  }
}
print "\n";

print "Wait after failure: $wait_after_failure seconds\n";
print "Executing run_sdrp script file ...\n";
print "Destination is $destdir\n";
print "Executable is $sdrp\n";
print "Running every $nextrev rev", ($nextrev == 1) ? '' : 's', "\n";
if ($min_rsdr_size > 0) {
    print "Minimum RSDR size $min_rsdr_size bytes\n";
}
print "\n";

#
# Get satellite number and constants based on flight number.
#
if ($fltnum == 16) {
  $sat = 1;
  $const = 2;
} elsif ($fltnum == 17) {
  $sat = 2;
  $const = 4;
} elsif ($fltnum == 18) {
  $sat = 3;
  $const = 3;
} elsif ($fltnum == 19) {
  $sat = 4;
  $const = 1;
} elsif ($fltnum == 20) {
  $sat = 5;
  $const = 5;
}

#
# We build a list of rev numbers, rather than simply iterating through them in
# a for() loop, because we want to handle the case where we've finished all
# requested revs but some of them need to be retried.  With a for() loop, the
# loop might exit before a rev comes back needing to be retried.
#
my $looking = "Looking for data files...";
print $looking;

#
# First look in Processed/datafiles.txt which is much faster than using a
# 'find' command.  If this file doesn't exist, fall back on find.
#
my @all_rsdrs;
if (open(FILE_LIST, "</scratch/users/m26814/newrsdrfiles/datafiles.txt")) {
  chomp(@all_rsdrs = <FILE_LIST>);
  close(FILE_LIST);
  @all_rsdrs = grep(/\/msf${fltnum}/, @all_rsdrs);
} else {
  chomp(@all_rsdrs = `find /scratch/users/m26814/newrsdrfiles/ -type f -name \\*.dat -o -name \\*.dat.gz`);
  
}

#
# Then add any new (unprocessed) files using a quick find.
#
chomp(my @new_rsdrs = `find /scratch/users/m26814/newrsdrfiles/ -type f -name \\*.dat -o -name \\*.dat.gz`);

push(@all_rsdrs, @new_rsdrs);
#
# Build the rev list.
#   - If we were given start/stop rev numbers, look for all revs in between and
#     increment rev number by $nextrev.
#   - If we were given start/stop dates, include all revs (no skipping by
#     $nextrev) and increment the date by 1 day as we search.
#
if ($stop =~ /^\d{8}$/ && $start =~ /^(\d\d\d\d)(\d\d)(\d\d)$/) {
   my $start_year = $1;
   my $start_mon = $2;
   my $start_day = $3;
   $stop =~ /^(\d\d\d\d)(\d\d)(\d\d)$/;
   my $stop_year = $1;
   my $stop_mon = $2;
   my $stop_day = $3;
   my $start_time = timegm(0, 0, 10, $start_day, $start_mon-1, $start_year);
   my $stop_time = timegm(0, 0, 12, $stop_day, $stop_mon-1, $stop_year);
   my $nsecs = $stop_time - $start_time + 86400;
   for (my $time = $start_time; $time <= $stop_time; $time += 86400) {
       my @gmt = gmtime($time);
       my $date = sprintf("%04d%02d%02d", $gmt[5]+1900, $gmt[4]+1, $gmt[3]);
       @revrsdr = grep(/\/$date\/msf.*\.dat(\.gz)?$/, @all_rsdrs);

       push(@revlist, @revrsdr);
       my $pct = int(100 * ($time - $start_time) / $nsecs);
       print "\r$looking$pct%"; 

   }
} else {
  my $nrevs = $stop - $start + 1;
  for (my $rev = $start; $rev <= $stop; $rev += $nextrev) {
    my $rev5 = $rev;
    @revrsdr = grep(/\/F${fltnum}_${rev5}\.dat(\.gz)?$/, @all_rsdrs);
    push(@revlist, @revrsdr);
    my $pct = int(100 * ($rev - $start) / $nrevs);
    print "\r$looking$pct%";
  }
  
}
print "\r${looking}100%\n\n";

#
# This is the main loop.  Normally, it iterates through the requested rev
# numbers by pulling them out of @revlist.  If any files are marked for
# retry, we handle those in this iteration instead.  If there are no more
# files or revs to be done, we simply wait for all running machines to finish.
#
while ((my @retry = keys %retry_rsdr) || @revlist || &wait_for_child()) {
  if (@retry) {
    # If @retry has elements, it means they came from %retry_rsdr.  We
    # should delete those elements to avoid duplicating them in the loop
    # below.  The elements of %retry_rsdr are already filenames, so no
    # need to go out and find them.
    unshift(@revlist, @retry);
    foreach my $rsdr (@revrsdr) {
      delete $retry_rsdr{$rsdr};
    }
  }

  # We may have found multiple files for the same rev number, so loop through
  # all files here.

  while (@revlist) {
    # If a failed RSDR run came back while waiting above, the file
    # name will be stored as a key in %retry_rsdr.  Add any such files
    # to @revrsdr now, using unshift() to put them at the beginning of
    # the list.  This is really optional because the next outer loop will
    # catch it, but this gets retried files done sooner.
	unshift(@revlist, keys %retry_rsdr);

    my $rsdr = shift(@revlist);

    # Get the "rev" portion of the filename.  We use this as our unique
    # "extension" for all corresponding output files.
    my $rev_str = $rsdr;
    $rev_str =~ s|^.*/||g;		# Remove leading directories
    $rev_str =~ s|\.dat(\.gz)?$||;	# Remove '.dat' or '.dat.gz' extension
    $rev_str =~ s|^F${fltnum}_||o;	# Remove 'msfxx_' prefix

    # Rarely, we get two different files with the same rev number
    # but in a different date directory.  They have exactly the
    # same filename and therefore $rev_str, so we must modify
    # the string to be unique.
    my $use_rev_str = $rev_str;
    my $num = 1;

    # while (defined($rev_processed{$use_rev_str})) {
      # $use_rev_str = sprintf("${rev_str}-%02d", $num++);
    # }

    # Set this one as in use, remove it from the retry list if applicable.
    $rev_processed{$use_rev_str} = 1;
    delete $retry_rsdr{$rsdr} if (defined($retry_rsdr{$rsdr}));

    # If we have a minimum file size, check that now.  Skip this file if
    # it does not meet the minimum.
    if ($min_rsdr_size > 0) {
        my $size = (stat($rsdr))[7];
        my $min_size = $min_rsdr_size;
        if ($rsdr =~ /\.gz$/) { $min_size *= GZIP_COMPRESSION; }
        if ($size < $min_size) {
            print "* Skipping $use_rev_str because size $size < $min_size\n";
            next;
        }
    }

    # Run SDRP on a remote machine.
    my $sun = &get_free_sun();
    &fork_sdrp($sun, $use_rev_str, $rsdr);
  }
}

#
# Per-machine runtime statistics, sort by average runtime.
#
my %avgtime;
my $total_runs = 0;
foreach my $sun (keys %runtime) {
    $avgtime{$sun} = $runs{$sun} > 0 ? $runtime{$sun} / $runs{$sun} : 0;
}
print "\n\nRuntime statistics:\n";
foreach my $sun (sort { $avgtime{$a} <=> $avgtime{$b} } keys %avgtime) {
  my $avg = $runs{$sun} > 0 ? sprintf("%.1fs", $avgtime{$sun}) : '<no runs>';
  my $plural = ($runs{$sun} == 1) ? '' : 's';
  print "    $sun:	Avg ${avg},	$runs{$sun} total run$plural.\n";
  $total_runs += $runs{$sun};
}

#
# SDRP crash and fatal error statistics.
#
$LIST_SEPARATOR = "\n";
if (@sdrp_fatal_rsdrs) {
  my $num_fatal = @sdrp_fatal_rsdrs;
  my $plural = ($num_fatal == 1) ? '' : 's';
  print "\n\nThe following RSDR files caused SDRP fatal errors:\n";
  print "@sdrp_fatal_rsdrs\n";
  print "Total: $num_fatal file$plural.\n";
}
if (@sdrp_crash_rsdrs) {
  my $num_crash = @sdrp_crash_rsdrs;
  my $plural = ($num_crash == 1) ? '' : 's';
  print "\n\nThe following RSDR files crashed SDRP:\n";
  
  foreach my $rsdr (@sdrp_crash_rsdrs) {
    print "$rsdr\n";
    print "  => Output: $status_file{$rsdr}\n";
    print "  => Core:   $core_file{$rsdr}\n";
  }
  print "Total: $num_crash file$plural.\n";
}

#
# Total runtime.
#
my $sec = time - $script_start;
my $total_avg = $total_runs > 0 ? sprintf("%.1fs.", $sec / $total_runs) : '<no runs>';
my $day = int($sec / 86400);
my $hour = sprintf("%02d", int(($sec % 86400) / 3600));
my $min = sprintf("%02d", int(($sec % 3600) / 60));
$sec = sprintf("%02d", $sec % 60);
print "\n\nTotal runtime:	$day days, $hour:$min:${sec}\n";
print "Avg per rev:	$total_avg\n";

####################
# End main script. #
####################


sub fork_sdrp {
  # Creates a child process that runs SDRP on the remote machine.
  my $sun = shift;	# Machine to run on
  my $rev = shift;	# Unique rev number
  my $rsdr = shift;	# RSDR file
  my $pid = 0;		# Process ID of the child process
  my $time = time;	# System time in seconds

  return if ($finished);	# Skip processed if the user interrupted us.

  # If we didn't get a valid value for the Linux machine, there's probably
  # a big problem (like NFS isn't working at all??).  Bail out.
  unless ($sun) {
    print "\nMajor error?  Invalid machine '$sun' in the machine list.\n";
    print "Bailing out.\n";
    &interrupted();		# Clear everything.
    return;
  }

  # Build the run script for this rev.
  #my $tmp_dir = $local{$sun} ? LOCAL_TMP_DIR : TMP_DIR;
  my $tmp_dir = $destdir;
  my $run_sdrp = "$tmp_dir/run_sdrp_${time}_${$}_${sun}_F${fltnum}_${rev}";
  my $sdrp_status_file = "$run_sdrp.status";

  # Handle compressed RSDR files
  my $uncompressed_rsdr = $rsdr;
  my $decompress_cmd = '';
  my $post_delete_cmd = '';
  if ($uncompressed_rsdr =~ s/\.gz$//) {
      $uncompressed_rsdr =~ s|^.*/||;	# Delete leading directory
      $uncompressed_rsdr = "${run_sdrp}_$uncompressed_rsdr";
      $decompress_cmd = "gunzip -c \"$rsdr\" > \"$uncompressed_rsdr\"";
      $post_delete_cmd = "rm -f \"$uncompressed_rsdr\"";
  }

  # Try to get the date from the file's directory - use that to select the
  # geomagnetic field database.
  my $geomag = 'geomag.db';
  if ($rsdr =~ m|/(\d\d\d\d)(\d\d)\d\d/|) {
      my $year = $1;
      my $month = $2 + 0;
      if ($month > 6) {
          $geomag = "geomag_${year}.5.db";
      } else {
          $geomag = "geomag_${year}.db";
      }
      unless (-r "$ENV{GPS_DFDIR}$geomag") {
          $geomag = 'geomag.db';
      }
  }

  # When SDRP crashes, we'll save the core files.  Want to make sure
  # simultaneous crashes from different machines don't overwrite each other.
  my $sundir = "$destdir/$sun";
  mkdir $sundir, 0755 unless (-d $sundir);

  my $rmc = ($destdir =~ m#^/tmp(/|)$#) ? "rm -f $destdir/*.DAT $destdir/*.DIAG" : '';
  open(SCRIPT, ">$run_sdrp") || die "Couldn't create $run_sdrp: $!\n";
  print SCRIPT <<EOSCRIPT;
#!/bin/csh -f
if (! -d "$sundir") mkdir "$sundir"
cd "$sundir"
rm -f core
$rmc
$decompress_cmd
nice +19 "$sdrp" <<EOSDRP >& "$sdrp_status_file"
	$sat
	'$ENV{GPS_DFDIR}CONSTANTS$const.DAT'
	'$ENV{GPS_DFDIR}GLOBAL.PCF'
	'$ENV{GPS_DFDIR}SDRP.PCF'
	'$ENV{GPS_DFDIR}SDRP.OVR'
	'$uncompressed_rsdr'
	'$destdir/Doppler_F${fltnum}_$rev.DIAG'
	'$ENV{GPS_DFDIR}$geomag'
	'$ENV{GPS_DFDIR}sfctag.db'
	'$ENV{GPS_DFDIR}terhgt.db'
	'$ENV{GPS_DBDIR}1000ht.db'
	'$destdir/SDR_F${fltnum}_$rev.DAT'
	'$destdir/ENVs_F${fltnum}_$rev.DAT'
	'$destdir/TDR_F${fltnum}_$rev.DAT'
	'$destdir/SDR_F${fltnum}_$rev.DIAG'
	'$destdir/ENVs_F${fltnum}_$rev.DIAG'
	'$destdir/TDR_F${fltnum}_$rev.DIAG'
	'$destdir/RAW_F${fltnum}_$rev.DIAG'
	'$destdir/SDRP_F${fltnum}_$rev.DIAG'
	'$destdir/$sun.SUM'
	'$ENV{GPS_DFDIR}ICE_REGIONS_V2.DAT'
	'$ENV{GPS_DFDIR}UCAR_new_sclass.txt'
EOSDRP
echo Status: \$status >> "$sdrp_status_file"
$post_delete_cmd
EOSCRIPT
  close(SCRIPT);
  chmod 0755, $run_sdrp;

  # Fork a new process and run.
  if ($pid = fork) {			# Parent process
    # Setup signal handlers to exit gracefully in the parent.
    $SIG{INT} = \&interrupted;
    $SIG{QUIT} = \&interrupted;
    $SIG{TERM} = \&interrupted;

    # Keep track of data corresponding to this child.
    $pids{$pid} = $sun;
    $revs{$pid} = $rev;
    $file{$pid} = $rsdr;
    $run{$pid} = $run_sdrp;
    $status_file{$pid} = $sdrp_status_file;
    $starttime{$pid} = time;		# Time we started running

    return $pid;
  } else {
    # Child process: 'ssh' to the remote machine and then exit when done.
    my $ssh_status = 0;		# Exit status of 'ssh' command
    my $tries = 0;		# Number of times we've tried

    print "  Running rev $rev on $sun\n    => $rsdr\n";

    #
    # The resulting command on the remote system will look like this:
    #   $run_sdrp ; echo "Script: $status" >> $sdrp_status_file
    #
    if ($local{$sun}) {
      $ssh_status = system("$run_sdrp ; echo \"Script: \$status\" >> $sdrp_status_file");
    } else {
      sleep 1;	# Allow remote filesystem to catch up??
      $ssh_status = system('ssh', $sun, $run_sdrp, ';', 'echo', '"Script: $status"', '>>', $sdrp_status_file);
    }

    #
    # Check SDRP status: the run script echoes it to this file.
    #
    my $sdrp_status = 0;
    if (open(SDRP_STATUS, "<$sdrp_status_file")) {
      while (<SDRP_STATUS>) {
        chomp;
        # Generally, a system error code of 1 means SDRP didn't even run.
        # HOWEVER I can't find documentation to GUARANTEE that is always true.
        # Assuming it is, check for that first and set it to SDRP_NORUN if
	# true.  Otherwise use the status as reported.
        if (/^Status: (.+)$/) {
          $sdrp_status = ($1 == 1) ? SDRP_NORUN : ($1 + 0);
          last;
        }

        # If we get STOP: n, use n as the status because in that case SDRP
        # ran to completion.
        elsif (/STOP:? (.+)/) {
          $sdrp_status = $1 + 0;
          last;
        }

        # If the script failed to run, maybe there's a NFS problem?  We'll
        # retry on another machine in this case.
        elsif (/^Script: (.+)$/) {
          if ($1) {
            $sdrp_status = SDRP_NORUN;
          }
        }
      }
      close(SDRP_STATUS);
      my $sdrp_crashed = ($sdrp_status &&
                          ($sdrp_status != SDRP_FATAL &&
                           $sdrp_status != SDRP_IDL_FATAL &&
                           $sdrp_status != SDRP_NORUN));
      unlink $sdrp_status_file unless ($keep_files || $sdrp_crashed);
    }

    # If there's no status file, there must have been an NFS and/or
    # permission problem.  Mark it as SDRP_NORUN so the rev gets
    # retried on another machine.
    else {
      $sdrp_status = SDRP_NORUN;
    }

    #
    # Exit status signals to the parent whether we need to retry this rev on
    # another machine.
    #
    if ($ssh_status) {
      exit SSH_ERROR;
    } elsif ($sdrp_status == SDRP_FATAL || $sdrp_status == SDRP_IDL_FATAL) {
      exit SDRP_FATAL;
    } elsif ($sdrp_status == SDRP_NORUN) {
      exit SDRP_NORUN;
    } elsif ($sdrp_status) {
      exit SDRP_CRASH;
    }
    exit 0;
  }
}

sub get_free_sun {
  # Returns the name of the next available Linux machine.

  # Check for a non-busy machine.  If found, return that one.  If the machine has been
  # temporarily removed from the pool ($busy > num_processors), see if it is eligible to
  # come back yet.
  foreach my $sun (@linuxes) {
    if ($busy{$sun} < $num_processors{$sun}) {
      $busy{$sun} = $busy{$sun} + 1;
      return $sun;
    } elsif (($busy{$sun} > $num_processors{$sun}) && ($busy{$sun} < time)) {
      my $elapsed = time - $busy{$sun} + $wait_after_failure;
      print "~ Adding $sun back to the pool after $elapsed seconds.\n";
      $busy{$sun} = 1;
      return $sun;
    }
  }

  # Otherwise, wait for a child process to exit.  When it does, use that machine.
  return &wait_for_child();
}

sub wait_for_child {
  # Wait for a child process to finish, and clean up after it.

  my $pid = wait;	# Perl 'wait' returns the PID of the next child to exit.

  if ($pid > 0) {
    my $child_status = $CHILD_ERROR;	# Exit/error status of child
    my $rsdr = $file{$pid};		# RSDR file processed by child
    my $rev = $revs{$pid};		# Unique rev number processed by child
    my $sun = $pids{$pid};		# Linux machine used by child
    my $date = scalar localtime time;	# Printable date/time
    my $elapsed = time - $starttime{$pid};

    # Clean up: delete pertinent hash values.
    delete $pids{$pid};
    delete $file{$pid};
    delete $retry_rsdr{$rsdr} if (defined($retry_rsdr{$rsdr}));

    # Remove the run script.
    unlink $run{$pid} unless ($keep_files);	# Remove file
    delete $run{$pid};				# Delete hash value

    # Check child error status: 'perlvar' man page says the actual status
    # value is shifted over 8 bits.
    $child_status = $child_status >> 8;

    # If there's a 'core' file, save it for later analysis.
    my $core = "$destdir/$sun/core";
    if (-r $core) {
      my $new_core = "$destdir/core.$rev";
      system('mv', $core, "$new_core");
      $child_status = SDRP_CRASH;	# We must have crashed for sure.
      $core_file{$rsdr} = $new_core;
    }

    # No error: record run time.
    if ($child_status == 0) {
      $runtime{$sun} = $runtime{$sun} + $elapsed;
      $runs{$sun} = $runs{$sun} + 1;
      $crash{$sun} = 0;
      print sprintf("* $date Rev $rev finished ($sun, %.2fs).\n", $elapsed);
    }

    # Connection/ssh error or SDRP didn't even run: retry on another machine.
    elsif ($child_status == SSH_ERROR || $child_status == SDRP_NORUN) {
      if ($child_status == SSH_ERROR) {
        print "% $date Connection error with rev $rev ($sun, ${elapsed}s).\n";
      } else {
        print "@ $date SDRP didn't run rev $rev ($sun, ${elapsed}s)??\n";
      }
      print "    => Re-queueing for another machine...\n";

      # This rev is no longer considered processed so we can try it again.
      delete $rev_processed{$rev};
      $retry_rsdr{$rsdr} = 1;
      $crash{$sun} = 0;

      $busy{$sun} = time + $wait_after_failure;
      print "    => Removing $sun from the pool for $wait_after_failure seconds.\n";

      # We need to return the next free sun here since this one was removed from
      # the pool.  This could be recursive, but it should work out!
      $sun = &get_free_sun();
    }

    # SDRP fatal error: just make a note of it.  SDRP found an error condition
    # and exited in a controlled fashion.
    elsif ($child_status == SDRP_FATAL) {
      print "\$ $date SDRP aborted rev $rev ($sun, ${elapsed}s).\n";
      push(@sdrp_fatal_rsdrs, $rsdr);
      $crash{$sun} = 0;
    }

    # SDRP crash: make a note of it for later investigation.
    elsif ($child_status == SDRP_CRASH) {
      print "! $date SDRP crashed on F$fltnum rev $rev ($sun, ${elapsed}s).\n";
      push(@sdrp_crash_rsdrs, $rsdr);
      $crash{$sun} = $crash{$sun} + 1;

      if (-r $status_file{$pid}) {
        $status_file{$rsdr} = $status_file{$pid};
        delete $status_file{$pid};
      }

      # This machine is crashing a lot.  Should we do anything?
      #if ($crash{$sun} >= 5) {
      #  $busy{$sun} = time + $wait_after_failure;
      #  print "    => $sun is crashing a lot, removing from the pool for $wait_after_failure seconds.\n";
      #  $sun = &get_free_sun();
      #}
    }

    return $sun;
  }

  return 0;
}

sub check_dead_sun {
  # Returns 1 if the given Linux machine is dead, 0 if it is alive.
  my $sun = shift;	# Machine to check
  my $ping = '';	# Location of 'ping' executable
  my $preopt = '';	# Ping options that go before the machine name
  my $postopt = '';	# Ping options that go after the machine name
 
  # Setup the 'ping' command depending on what system is running this script.
  chomp(my $uname = `uname`);
  if ($uname eq 'Darwin') {	# Mac OS X (titan)
    $ping = '/sbin/ping';
    $preopt = '-c 1';
  } elsif ($uname eq 'Linux') {	# Linux
    $ping = '/bin/ping';
    $postopt = '-c 1 -W 1';
  } elsif ($uname eq 'IRIX') {	# SGI
    $ping = '/usr/etc/ping';
    $preopt = '-c 1 -w 1';
  }

  # Couldn't determine this system?  Assume all machines are dead!
  return 1 unless ($ping);

  # Run 'ping' and examine the results.
  if (open(PING, "$ping $preopt $sun $postopt|")) {
    while (<PING>) {
      if (/(\s0\s+(packets\s+)?received|no\s+answer\s+from)/) {
        # Found '0 packets received' or '0 received' or 'no answer from ...'
        close(PING);
        return ($num_processors{$sun} + 1);
      } elsif (/([0\.]+%\s+packet\s+loss|\s+is\s+alive)/) {
        # Found '0% packet loss' or '... is alive'
        close(PING);
        return 0;
      }
    }
  }
  close(PING);

  # Can't ping, must be dead!
  return ($num_processors{$sun} + 1);
}

sub usage {
  # Returns the usage string.
  my $usage = <<EOU;
Usage:	$0 fltnum startrev stoprev destination(optional)
Or	$0 fltnum startdate stopdate destination(optional)

Options:
	-n		Farm out jobs to machines on the network.  If not set,
			the default is to use only the local machine.

	-a machine	Add "machine" to the list of machines.

	-x machine	Exclude "machine" from the list of machines.

	-w wait		Wait 'wait' seconds after a machine fails to run a rev
			before trying that machine again.  Default: 900.

	-j n		Run only every 'n' revs.  Default 1 to run every rev.
			Ignored if start/stop are dates rather than revs.

	-k		Keep generated script files and exit status output
			(otherwise they are removed when finished)

	-s n		Minimum number of scans to run an RSDR file.  Files
			that are too small to contain this number of scans
			will be skipped (this determination is approximate).
			Default 0 means no minimum.
EOU

  return $usage;
}

sub interrupted {
  # Handle interrupt signals (such as Ctrl-C from the keyboard).  Child
  # processes won't catch these, so they'll perform the default action, which
  # is to exit immediately.  In the parent process, we'll truncate remaining
  # scan lists so the main loop finishes.

  @revlist = ();
  @revrsdr = ();
  %retry_rsdr = ();
  $finished = 1;
}

#####################################################################
#!/usr/bin/perl
#
#------------------------------------------------------------------------
# Run the Sensor Data Record Processor on multiple machines in parallel.
#------------------------------------------------------------------------
#processing_sdrp

use English;	# enable understandable long names for builtin perl variables
use strict;	# strict variable checking
use Time::HiRes qw(time);
use Sys::Hostname;
use Time::Local;

$OUTPUT_AUTOFLUSH = 1;

####################
# GLOBAL CONSTANTS #
####################
use constant SDRP_FATAL => 1;		# Must be the same as STOP 1 in FORTRAN
use constant SDRP_IDL_FATAL => 2;	# IDL GPS caught exception (bad data etc)
use constant SDRP_IDL_ERROR => 3;	# IDL error - equivalent to FORTRAN crash
use constant SDRP_NORUN => -1;		# SDRP didn't even run
use constant SDRP_CRASH => -2;		# SDRP ran but crashed
use constant SSH_ERROR  => -3;		# Connection/ssh error

use constant BYTES_PER_SCAN => 4700;	# Average bytes of RSDR per SSMIS scan
use constant GZIP_COMPRESSION => 0.72;	# Average compression ratio for gzipped
					# RSDR files

use constant TMP_DIR	   => '/home/data/dmsp/sdrp';	# Temp/scratch dir
use constant LOCAL_TMP_DIR => '/data/dmsp/sdrp';	# Local temp/scratch dir

####################
# GLOBAL VARIABLES #
####################

my %default_linuxes = (	# List of default Linux machines to use.  The numbers
			# determine the sort order when starting out.  They
			# don't have to be unique.
    rain	=> 1,
    typhoon	=> 1,
);

my %num_processors = (	# Number of processors to use on each machine.  If not
    rain	=> 8,	# listed here, assume 1.
    typhoon	=> 8,
);

my %common_hostname = (	# When determining the local hostname, wind/vector
			# will return adevwh01/adevwh02 instead of wind/vector.
			# This maps from one to the other.
    'ssmis-rhwks01.northgrum.com'    =>'rain',
    'ssmis-rhwks02.northgrum.com'    =>'typhoon',

);


my @linuxes;		# Working list of Linux machines: combination of defaults
			# and user-specified.
my $local_only = 1;	# True (1) if we should only use the local machine
			# (don't farm out jobs to networked machines).
			#
my %local;		# KEY:   a machine name.
			# VALUE: true if the machine is this machine; we bypass
			#        ssh for this machine and just run directly.
			#
my @revlist;		# List of rev numbers requested to run.
my @main_args;		# Primary command-line arguments: flight number, start
			# rev, stop rev, output dir.
my @sdrp_crash_rsdrs;	# List of RSDR files that got SDRP fatal errors.
my @sdrp_fatal_rsdrs;	# List of RSDR files that crashed SDRP.
my @revrsdr;		# List of RSDR files to run in the current iteration.


my %busy;		# KEY:   a machine name.
			# VALUE: number of processors in use, or
			#        system time value after which the machine will
			#        be considered available again.

my %pids;		# KEY:   pid of a child process.
			# VALUE: the machine being used to run this process.

my %file;		# KEY:   pid of a child process.
			# VALUE: the RSDR file being run by this process.

my %revs;		# KEY:   pid of a child process.
			# Value: unique rev number being run by this process.

my %run;		# KEY:   pid of a child process.
			# Value: the run script file being used by this process.

my %rev_processed;	# KEY:   unique rev number.
			# Value: true (1) if this rev is being (or has been)
			#        processed.

my %retry_rsdr;		# KEY:   name of an RSDR file that needs to be retried
			#        because the machine running it must have failed.
			# VALUE: unused.

my %starttime;		# KEY:   a process ID (PID).
			# VALUE: timestamp of script start for that child PID.

my %runtime;		# KEY:   a machine name.
			# VALUE: total run time of all revs on that machine.

my %runs;		# KEY:   a machine name.
			# VALUE: total number of SDRP runs on that machine.

my %crash;		# KEY:   a machine name.
			# VALUE: number of crashes for this machine since the
			#        last good run.

my %core_file;		# KEY:   name of an RSDR file that crashed SDRP
			# VALUE: name of the corresponding core file

my %status_file;	# KEY:   a process ID (PID) or name of an RSDR file
			#        that crashed SDRP
			# VALUE: the output/status file from this process

my $sdrp;		# Path to SDRP executable.
my $fltnum;		# Flight number (user-specified).
my $start;		# Start rev (user-specified).
my $stop;		# Stop rev (user-specified).
my $destdir;		# Output directory (user-specified or GPS_ODIR).
my $sat = 1;		# Satellite number.
my $const = 1;		# Constants file number.
my $finished = 0;	# True if we should finish now (user-interrupted).

my $wait_after_failure = 900;	# Default time to remove a machine from the pool
				# after it fails to run a particular rev.
				# Maybe it's just temporarily down, so we don't
				# want to remove it permanently from the pool.

my $nextrev = 1;	# Number of revs to the next rev when moving forward.
			# Default of 1 means process every rev (go 1 forward
			# each time).

my $keep_files = 0;	# True (1) if we should keep generated script files
			# and exit status output files

my $min_rsdr_size = 0;	# Minimum file size to run an RSDR file.  If positive,
			# files below this size will be skipped.

##############
# BEGIN CODE #
##############

my $script_start = time;

#
# Get command line arguments.
#
my $arg = shift;
while (defined($arg)) {
  # Add a machine to the list.
  if ($arg eq '-a') {
    my $add = lc shift;
    if (defined($add)) {
      push(@linuxes, $add);
    }
  }

  # Exclude a machine from the default list.
  elsif ($arg eq '-x') {
    my $exclude = lc shift;
    if (defined($exclude)) {
      delete $default_linuxes{$exclude};
    }
  }

  # Wait before adding a failed machine back to the list.
  elsif ($arg eq '-w') {
    my $wait = (shift) + 0;
    if ($wait > 0) {
      $wait_after_failure = $wait;
    }
  }

  # Run every 'j' revs
  elsif ($arg eq '-j') {
    $nextrev = (shift) + 0;
    if ($nextrev < 1) {
      $nextrev = 1;
    }
  }

  # Keep intermediate (script/status) files.
  elsif ($arg eq '-k') {
    $keep_files = 1;
  }

  # Minimum approximate scans to run an RSDR file.
  elsif ($arg eq '-s') {
    $min_rsdr_size = ((shift) + 0) * BYTES_PER_SCAN;
  }

  # Use networked machines in addition to local.
  elsif ($arg eq '-n') {
    $local_only = 0;
  }

  # This must be one of the primary four arguments.  Save it for below.
  else {
    push(@main_args, $arg);
  }

  $arg = shift;
}

#
# Get main arguments in order.
#
$fltnum = shift(@main_args);
$start = shift(@main_args);
$stop = shift(@main_args);
$destdir = shift(@main_args);

#
# Make sure the num_processors list matches the default_linuxes list.
# Add any that aren't listed, assuming just 1 processor for those.
#
my $hostname = Sys::Hostname::hostname();
if (defined($common_hostname{$hostname})) {
    $hostname = $common_hostname{$hostname};
}
foreach my $linux (keys %default_linuxes) {
  unless (defined($num_processors{$linux})) {
    $num_processors{$linux} = 1;
  }
  # If the name matches our hostname, this is the local machine.
  # Use this info later to bypass the ssh connection, and just run directly.
  if ($linux =~ /^$hostname$/io) {
    $local{$linux} = 1;
  } elsif ($local_only) {
    delete $default_linuxes{$linux};
  }
}

#
# Add default machines to the working list.  User-added machines will be ahead of them.
#
push(@linuxes, sort { $default_linuxes{$a} <=> $default_linuxes{$b} } keys %default_linuxes);

#
# Check flight number, start and stop rev numbers.
#
unless (defined($fltnum) && defined($start) && defined($stop)) {
  die &usage();
}

my @env_dirs = (
  'GPS_DFDIR',
  'GPS_DBDIR',
  'GPS_EXEDIR',
);

#
# If we're farming jobs to networked machines, the environment paths ought
# to be /home/... and not local.  Check if we're in /Users/... and convert
# that to /home/hostname/...
#

unless ($local_only) {
  my $home_dir = "/home/$hostname";
  my $home_data = (-l '/home/data') ? '/home/data' : '/home/data2';
  
  foreach my $dir (@env_dirs) {
    if ($ENV{$dir} =~ /^\/Users\// && -d $home_dir) {
      $ENV{$dir} =~ s/^\/Users/$home_dir/o;
    } elsif ($ENV{$dir} =~ /^\/data\// && -l $home_data) {
      $ENV{$dir} =~ s/^\/data/$home_data/o;
    }
  }
}
foreach my $dir (@env_dirs) { print "$dir=$ENV{$dir}\n"; }

#
# Check that environment is properly setup.
#
foreach my $dir (@env_dirs) {
  unless (-d $ENV{$dir}) {
    die "Please source gps_setdir ($dir '$ENV{$dir}' is not a dir).\n";
  }
}
my $sdrp_exe = $ENV{SDRP_EXE} || 'sdrp';
$sdrp = "$ENV{GPS_EXEDIR}$sdrp_exe";
die "Can't find sdrp or is not executable ('$sdrp')\n" unless (-x $sdrp);

#
# Check destination directory: default if not set is $GPS_ODIR.
#
if (!defined($destdir)) {
  $destdir = $ENV{GPS_ODIR};
}
if ((! -d $destdir) || (! -w $destdir)) {
  die "Destination '$destdir' is not a directory or not writable.\n" . &usage();
}

#
# If any machines don't respond, consider them eternally busy.
#
for my $sun (@linuxes) {
  print "Checking $sun... ";
  $busy{$sun} = &check_dead_sun($sun);
  if ($busy{$sun}) {
    print "offline, not using.\n";
    $busy{$sun} = time + $wait_after_failure;
  } else {
    print "ok.\n";
  }
}
print "\n";

print "Wait after failure: $wait_after_failure seconds\n";
print "Executing run_sdrp script file ...\n";
print "Destination is $destdir\n";
print "Executable is $sdrp\n";
print "Running every $nextrev rev", ($nextrev == 1) ? '' : 's', "\n";
if ($min_rsdr_size > 0) {
    print "Minimum RSDR size $min_rsdr_size bytes\n";
}
print "\n";

#
# Get satellite number and constants based on flight number.
#
if ($fltnum == 16) {
  $sat = 1;
  $const = 2;
} elsif ($fltnum == 17) {
  $sat = 2;
  $const = 4;
} elsif ($fltnum == 18) {
  $sat = 3;
  $const = 3;
} elsif ($fltnum == 19) {
  $sat = 4;
  $const = 1;
} elsif ($fltnum == 20) {
  $sat = 5;
  $const = 5;
}

#
# We build a list of rev numbers, rather than simply iterating through them in
# a for() loop, because we want to handle the case where we've finished all
# requested revs but some of them need to be retried.  With a for() loop, the
# loop might exit before a rev comes back needing to be retried.
#
my $looking = "Looking for data files...";
print $looking;

#
# First look in Processed/datafiles.txt which is much faster than using a
# 'find' command.  If this file doesn't exist, fall back on find.
#
my @all_rsdrs;
if (open(FILE_LIST, "</scratch/users/m26814/newrsdrfiles/datafiles.txt")) {
  chomp(@all_rsdrs = <FILE_LIST>);
  close(FILE_LIST);
  @all_rsdrs = grep(/\/msf${fltnum}/, @all_rsdrs);
} else {
  chomp(@all_rsdrs = `find /scratch/users/m26814/newrsdrfiles/ -type f -name \\*.dat -o -name \\*.dat.gz`);
  
}

#
# Then add any new (unprocessed) files using a quick find.
#
chomp(my @new_rsdrs = `find /scratch/users/m26814/newrsdrfiles/ -type f -name \\*.dat -o -name \\*.dat.gz`);

push(@all_rsdrs, @new_rsdrs);
#
# Build the rev list.
#   - If we were given start/stop rev numbers, look for all revs in between and
#     increment rev number by $nextrev.
#   - If we were given start/stop dates, include all revs (no skipping by
#     $nextrev) and increment the date by 1 day as we search.
#
if ($stop =~ /^\d{8}$/ && $start =~ /^(\d\d\d\d)(\d\d)(\d\d)$/) {
   my $start_year = $1;
   my $start_mon = $2;
   my $start_day = $3;
   $stop =~ /^(\d\d\d\d)(\d\d)(\d\d)$/;
   my $stop_year = $1;
   my $stop_mon = $2;
   my $stop_day = $3;
   my $start_time = timegm(0, 0, 10, $start_day, $start_mon-1, $start_year);
   my $stop_time = timegm(0, 0, 12, $stop_day, $stop_mon-1, $stop_year);
   my $nsecs = $stop_time - $start_time + 86400;
   for (my $time = $start_time; $time <= $stop_time; $time += 86400) {
       my @gmt = gmtime($time);
       my $date = sprintf("%04d%02d%02d", $gmt[5]+1900, $gmt[4]+1, $gmt[3]);
       @revrsdr = grep(/\/$date\/msf.*\.dat(\.gz)?$/, @all_rsdrs);

       push(@revlist, @revrsdr);
       my $pct = int(100 * ($time - $start_time) / $nsecs);
       print "\r$looking$pct%"; 

   }
} else {
  my $nrevs = $stop - $start + 1;
  for (my $rev = $start; $rev <= $stop; $rev += $nextrev) {
    my $rev5 = $rev;
    @revrsdr = grep(/\/F${fltnum}_${rev5}\.dat(\.gz)?$/, @all_rsdrs);
    push(@revlist, @revrsdr);
    my $pct = int(100 * ($rev - $start) / $nrevs);
    print "\r$looking$pct%";
  }
  
}
print "\r${looking}100%\n\n";

#
# This is the main loop.  Normally, it iterates through the requested rev
# numbers by pulling them out of @revlist.  If any files are marked for
# retry, we handle those in this iteration instead.  If there are no more
# files or revs to be done, we simply wait for all running machines to finish.
#
while ((my @retry = keys %retry_rsdr) || @revlist || &wait_for_child()) {
  if (@retry) {
    # If @retry has elements, it means they came from %retry_rsdr.  We
    # should delete those elements to avoid duplicating them in the loop
    # below.  The elements of %retry_rsdr are already filenames, so no
    # need to go out and find them.
    unshift(@revlist, @retry);
    foreach my $rsdr (@revrsdr) {
      delete $retry_rsdr{$rsdr};
    }
  }

  # We may have found multiple files for the same rev number, so loop through
  # all files here.

  while (@revlist) {
    # If a failed RSDR run came back while waiting above, the file
    # name will be stored as a key in %retry_rsdr.  Add any such files
    # to @revrsdr now, using unshift() to put them at the beginning of
    # the list.  This is really optional because the next outer loop will
    # catch it, but this gets retried files done sooner.
	unshift(@revlist, keys %retry_rsdr);

    my $rsdr = shift(@revlist);

    # Get the "rev" portion of the filename.  We use this as our unique
    # "extension" for all corresponding output files.
    my $rev_str = $rsdr;
    $rev_str =~ s|^.*/||g;		# Remove leading directories
    $rev_str =~ s|\.dat(\.gz)?$||;	# Remove '.dat' or '.dat.gz' extension
    $rev_str =~ s|^F${fltnum}_||o;	# Remove 'msfxx_' prefix

    # Rarely, we get two different files with the same rev number
    # but in a different date directory.  They have exactly the
    # same filename and therefore $rev_str, so we must modify
    # the string to be unique.
    my $use_rev_str = $rev_str;
    my $num = 1;

    # while (defined($rev_processed{$use_rev_str})) {
      # $use_rev_str = sprintf("${rev_str}-%02d", $num++);
    # }

    # Set this one as in use, remove it from the retry list if applicable.
    $rev_processed{$use_rev_str} = 1;
    delete $retry_rsdr{$rsdr} if (defined($retry_rsdr{$rsdr}));

    # If we have a minimum file size, check that now.  Skip this file if
    # it does not meet the minimum.
    if ($min_rsdr_size > 0) {
        my $size = (stat($rsdr))[7];
        my $min_size = $min_rsdr_size;
        if ($rsdr =~ /\.gz$/) { $min_size *= GZIP_COMPRESSION; }
        if ($size < $min_size) {
            print "* Skipping $use_rev_str because size $size < $min_size\n";
            next;
        }
    }

    # Run SDRP on a remote machine.
    my $sun = &get_free_sun();
    &fork_sdrp($sun, $use_rev_str, $rsdr);
  }
}

#
# Per-machine runtime statistics, sort by average runtime.
#
my %avgtime;
my $total_runs = 0;
foreach my $sun (keys %runtime) {
    $avgtime{$sun} = $runs{$sun} > 0 ? $runtime{$sun} / $runs{$sun} : 0;
}
print "\n\nRuntime statistics:\n";
foreach my $sun (sort { $avgtime{$a} <=> $avgtime{$b} } keys %avgtime) {
  my $avg = $runs{$sun} > 0 ? sprintf("%.1fs", $avgtime{$sun}) : '<no runs>';
  my $plural = ($runs{$sun} == 1) ? '' : 's';
  print "    $sun:	Avg ${avg},	$runs{$sun} total run$plural.\n";
  $total_runs += $runs{$sun};
}

#
# SDRP crash and fatal error statistics.
#
$LIST_SEPARATOR = "\n";
if (@sdrp_fatal_rsdrs) {
  my $num_fatal = @sdrp_fatal_rsdrs;
  my $plural = ($num_fatal == 1) ? '' : 's';
  print "\n\nThe following RSDR files caused SDRP fatal errors:\n";
  print "@sdrp_fatal_rsdrs\n";
  print "Total: $num_fatal file$plural.\n";
}
if (@sdrp_crash_rsdrs) {
  my $num_crash = @sdrp_crash_rsdrs;
  my $plural = ($num_crash == 1) ? '' : 's';
  print "\n\nThe following RSDR files crashed SDRP:\n";
  
  foreach my $rsdr (@sdrp_crash_rsdrs) {
    print "$rsdr\n";
    print "  => Output: $status_file{$rsdr}\n";
    print "  => Core:   $core_file{$rsdr}\n";
  }
  print "Total: $num_crash file$plural.\n";
}

#
# Total runtime.
#
my $sec = time - $script_start;
my $total_avg = $total_runs > 0 ? sprintf("%.1fs.", $sec / $total_runs) : '<no runs>';
my $day = int($sec / 86400);
my $hour = sprintf("%02d", int(($sec % 86400) / 3600));
my $min = sprintf("%02d", int(($sec % 3600) / 60));
$sec = sprintf("%02d", $sec % 60);
print "\n\nTotal runtime:	$day days, $hour:$min:${sec}\n";
print "Avg per rev:	$total_avg\n";

####################
# End main script. #
####################


sub fork_sdrp {
  # Creates a child process that runs SDRP on the remote machine.
  my $sun = shift;	# Machine to run on
  my $rev = shift;	# Unique rev number
  my $rsdr = shift;	# RSDR file
  my $pid = 0;		# Process ID of the child process
  my $time = time;	# System time in seconds

  return if ($finished);	# Skip processed if the user interrupted us.

  # If we didn't get a valid value for the Linux machine, there's probably
  # a big problem (like NFS isn't working at all??).  Bail out.
  unless ($sun) {
    print "\nMajor error?  Invalid machine '$sun' in the machine list.\n";
    print "Bailing out.\n";
    &interrupted();		# Clear everything.
    return;
  }

  # Build the run script for this rev.
  #my $tmp_dir = $local{$sun} ? LOCAL_TMP_DIR : TMP_DIR;
  my $tmp_dir = $destdir;
  my $run_sdrp = "$tmp_dir/run_sdrp_${time}_${$}_${sun}_F${fltnum}_${rev}";
  my $sdrp_status_file = "$run_sdrp.status";

  # Handle compressed RSDR files
  my $uncompressed_rsdr = $rsdr;
  my $decompress_cmd = '';
  my $post_delete_cmd = '';
  if ($uncompressed_rsdr =~ s/\.gz$//) {
      $uncompressed_rsdr =~ s|^.*/||;	# Delete leading directory
      $uncompressed_rsdr = "${run_sdrp}_$uncompressed_rsdr";
      $decompress_cmd = "gunzip -c \"$rsdr\" > \"$uncompressed_rsdr\"";
      $post_delete_cmd = "rm -f \"$uncompressed_rsdr\"";
  }

  # Try to get the date from the file's directory - use that to select the
  # geomagnetic field database.
  my $geomag = 'geomag.db';
  if ($rsdr =~ m|/(\d\d\d\d)(\d\d)\d\d/|) {
      my $year = $1;
      my $month = $2 + 0;
      if ($month > 6) {
          $geomag = "geomag_${year}.5.db";
      } else {
          $geomag = "geomag_${year}.db";
      }
      unless (-r "$ENV{GPS_DFDIR}$geomag") {
          $geomag = 'geomag.db';
      }
  }

  # When SDRP crashes, we'll save the core files.  Want to make sure
  # simultaneous crashes from different machines don't overwrite each other.
  my $sundir = "$destdir/$sun";
  mkdir $sundir, 0755 unless (-d $sundir);

  my $rmc = ($destdir =~ m#^/tmp(/|)$#) ? "rm -f $destdir/*.DAT $destdir/*.DIAG" : '';
  open(SCRIPT, ">$run_sdrp") || die "Couldn't create $run_sdrp: $!\n";
  print SCRIPT <<EOSCRIPT;
#!/bin/csh -f
if (! -d "$sundir") mkdir "$sundir"
cd "$sundir"
rm -f core
$rmc
$decompress_cmd
nice +19 "$sdrp" <<EOSDRP >& "$sdrp_status_file"
	$sat
	'$ENV{GPS_DFDIR}CONSTANTS$const.DAT'
	'$ENV{GPS_DFDIR}GLOBAL.PCF'
	'$ENV{GPS_DFDIR}SDRP.PCF'
	'$ENV{GPS_DFDIR}SDRP.OVR'
	'$uncompressed_rsdr'
	'$destdir/Doppler_F${fltnum}_$rev.DIAG'
	'$ENV{GPS_DFDIR}$geomag'
	'$ENV{GPS_DFDIR}sfctag.db'
	'$ENV{GPS_DFDIR}terhgt.db'
	'$ENV{GPS_DBDIR}1000ht.db'
	'$destdir/SDR_F${fltnum}_$rev.DAT'
	'$destdir/ENVs_F${fltnum}_$rev.DAT'
	'$destdir/TDR_F${fltnum}_$rev.DAT'
	'$destdir/SDR_F${fltnum}_$rev.DIAG'
	'$destdir/ENVs_F${fltnum}_$rev.DIAG'
	'$destdir/TDR_F${fltnum}_$rev.DIAG'
	'$destdir/RAW_F${fltnum}_$rev.DIAG'
	'$destdir/SDRP_F${fltnum}_$rev.DIAG'
	'$destdir/$sun.SUM'
	'$ENV{GPS_DFDIR}ICE_REGIONS_V2.DAT'
	'$ENV{GPS_DFDIR}UCAR_new_sclass.txt'
EOSDRP
echo Status: \$status >> "$sdrp_status_file"
$post_delete_cmd
EOSCRIPT
  close(SCRIPT);
  chmod 0755, $run_sdrp;

  # Fork a new process and run.
  if ($pid = fork) {			# Parent process
    # Setup signal handlers to exit gracefully in the parent.
    $SIG{INT} = \&interrupted;
    $SIG{QUIT} = \&interrupted;
    $SIG{TERM} = \&interrupted;

    # Keep track of data corresponding to this child.
    $pids{$pid} = $sun;
    $revs{$pid} = $rev;
    $file{$pid} = $rsdr;
    $run{$pid} = $run_sdrp;
    $status_file{$pid} = $sdrp_status_file;
    $starttime{$pid} = time;		# Time we started running

    return $pid;
  } else {
    # Child process: 'ssh' to the remote machine and then exit when done.
    my $ssh_status = 0;		# Exit status of 'ssh' command
    my $tries = 0;		# Number of times we've tried

    print "  Running rev $rev on $sun\n    => $rsdr\n";

    #
    # The resulting command on the remote system will look like this:
    #   $run_sdrp ; echo "Script: $status" >> $sdrp_status_file
    #
    if ($local{$sun}) {
      $ssh_status = system("$run_sdrp ; echo \"Script: \$status\" >> $sdrp_status_file");
    } else {
      sleep 1;	# Allow remote filesystem to catch up??
      $ssh_status = system('ssh', $sun, $run_sdrp, ';', 'echo', '"Script: $status"', '>>', $sdrp_status_file);
    }

    #
    # Check SDRP status: the run script echoes it to this file.
    #
    my $sdrp_status = 0;
    if (open(SDRP_STATUS, "<$sdrp_status_file")) {
      while (<SDRP_STATUS>) {
        chomp;
        # Generally, a system error code of 1 means SDRP didn't even run.
        # HOWEVER I can't find documentation to GUARANTEE that is always true.
        # Assuming it is, check for that first and set it to SDRP_NORUN if
	# true.  Otherwise use the status as reported.
        if (/^Status: (.+)$/) {
          $sdrp_status = ($1 == 1) ? SDRP_NORUN : ($1 + 0);
          last;
        }

        # If we get STOP: n, use n as the status because in that case SDRP
        # ran to completion.
        elsif (/STOP:? (.+)/) {
          $sdrp_status = $1 + 0;
          last;
        }

        # If the script failed to run, maybe there's a NFS problem?  We'll
        # retry on another machine in this case.
        elsif (/^Script: (.+)$/) {
          if ($1) {
            $sdrp_status = SDRP_NORUN;
          }
        }
      }
      close(SDRP_STATUS);
      my $sdrp_crashed = ($sdrp_status &&
                          ($sdrp_status != SDRP_FATAL &&
                           $sdrp_status != SDRP_IDL_FATAL &&
                           $sdrp_status != SDRP_NORUN));
      unlink $sdrp_status_file unless ($keep_files || $sdrp_crashed);
    }

    # If there's no status file, there must have been an NFS and/or
    # permission problem.  Mark it as SDRP_NORUN so the rev gets
    # retried on another machine.
    else {
      $sdrp_status = SDRP_NORUN;
    }

    #
    # Exit status signals to the parent whether we need to retry this rev on
    # another machine.
    #
    if ($ssh_status) {
      exit SSH_ERROR;
    } elsif ($sdrp_status == SDRP_FATAL || $sdrp_status == SDRP_IDL_FATAL) {
      exit SDRP_FATAL;
    } elsif ($sdrp_status == SDRP_NORUN) {
      exit SDRP_NORUN;
    } elsif ($sdrp_status) {
      exit SDRP_CRASH;
    }
    exit 0;
  }
}

sub get_free_sun {
  # Returns the name of the next available Linux machine.

  # Check for a non-busy machine.  If found, return that one.  If the machine has been
  # temporarily removed from the pool ($busy > num_processors), see if it is eligible to
  # come back yet.
  foreach my $sun (@linuxes) {
    if ($busy{$sun} < $num_processors{$sun}) {
      $busy{$sun} = $busy{$sun} + 1;
      return $sun;
    } elsif (($busy{$sun} > $num_processors{$sun}) && ($busy{$sun} < time)) {
      my $elapsed = time - $busy{$sun} + $wait_after_failure;
      print "~ Adding $sun back to the pool after $elapsed seconds.\n";
      $busy{$sun} = 1;
      return $sun;
    }
  }

  # Otherwise, wait for a child process to exit.  When it does, use that machine.
  return &wait_for_child();
}

sub wait_for_child {
  # Wait for a child process to finish, and clean up after it.

  my $pid = wait;	# Perl 'wait' returns the PID of the next child to exit.

  if ($pid > 0) {
    my $child_status = $CHILD_ERROR;	# Exit/error status of child
    my $rsdr = $file{$pid};		# RSDR file processed by child
    my $rev = $revs{$pid};		# Unique rev number processed by child
    my $sun = $pids{$pid};		# Linux machine used by child
    my $date = scalar localtime time;	# Printable date/time
    my $elapsed = time - $starttime{$pid};

    # Clean up: delete pertinent hash values.
    delete $pids{$pid};
    delete $file{$pid};
    delete $retry_rsdr{$rsdr} if (defined($retry_rsdr{$rsdr}));

    # Remove the run script.
    unlink $run{$pid} unless ($keep_files);	# Remove file
    delete $run{$pid};				# Delete hash value

    # Check child error status: 'perlvar' man page says the actual status
    # value is shifted over 8 bits.
    $child_status = $child_status >> 8;

    # If there's a 'core' file, save it for later analysis.
    my $core = "$destdir/$sun/core";
    if (-r $core) {
      my $new_core = "$destdir/core.$rev";
      system('mv', $core, "$new_core");
      $child_status = SDRP_CRASH;	# We must have crashed for sure.
      $core_file{$rsdr} = $new_core;
    }

    # No error: record run time.
    if ($child_status == 0) {
      $runtime{$sun} = $runtime{$sun} + $elapsed;
      $runs{$sun} = $runs{$sun} + 1;
      $crash{$sun} = 0;
      print sprintf("* $date Rev $rev finished ($sun, %.2fs).\n", $elapsed);
    }

    # Connection/ssh error or SDRP didn't even run: retry on another machine.
    elsif ($child_status == SSH_ERROR || $child_status == SDRP_NORUN) {
      if ($child_status == SSH_ERROR) {
        print "% $date Connection error with rev $rev ($sun, ${elapsed}s).\n";
      } else {
        print "@ $date SDRP didn't run rev $rev ($sun, ${elapsed}s)??\n";
      }
      print "    => Re-queueing for another machine...\n";

      # This rev is no longer considered processed so we can try it again.
      delete $rev_processed{$rev};
      $retry_rsdr{$rsdr} = 1;
      $crash{$sun} = 0;

      $busy{$sun} = time + $wait_after_failure;
      print "    => Removing $sun from the pool for $wait_after_failure seconds.\n";

      # We need to return the next free sun here since this one was removed from
      # the pool.  This could be recursive, but it should work out!
      $sun = &get_free_sun();
    }

    # SDRP fatal error: just make a note of it.  SDRP found an error condition
    # and exited in a controlled fashion.
    elsif ($child_status == SDRP_FATAL) {
      print "\$ $date SDRP aborted rev $rev ($sun, ${elapsed}s).\n";
      push(@sdrp_fatal_rsdrs, $rsdr);
      $crash{$sun} = 0;
    }

    # SDRP crash: make a note of it for later investigation.
    elsif ($child_status == SDRP_CRASH) {
      print "! $date SDRP crashed on F$fltnum rev $rev ($sun, ${elapsed}s).\n";
      push(@sdrp_crash_rsdrs, $rsdr);
      $crash{$sun} = $crash{$sun} + 1;

      if (-r $status_file{$pid}) {
        $status_file{$rsdr} = $status_file{$pid};
        delete $status_file{$pid};
      }

      # This machine is crashing a lot.  Should we do anything?
      #if ($crash{$sun} >= 5) {
      #  $busy{$sun} = time + $wait_after_failure;
      #  print "    => $sun is crashing a lot, removing from the pool for $wait_after_failure seconds.\n";
      #  $sun = &get_free_sun();
      #}
    }

    return $sun;
  }

  return 0;
}

sub check_dead_sun {
  # Returns 1 if the given Linux machine is dead, 0 if it is alive.
  my $sun = shift;	# Machine to check
  my $ping = '';	# Location of 'ping' executable
  my $preopt = '';	# Ping options that go before the machine name
  my $postopt = '';	# Ping options that go after the machine name
 
  # Setup the 'ping' command depending on what system is running this script.
  chomp(my $uname = `uname`);
  if ($uname eq 'Darwin') {	# Mac OS X (titan)
    $ping = '/sbin/ping';
    $preopt = '-c 1';
  } elsif ($uname eq 'Linux') {	# Linux
    $ping = '/bin/ping';
    $postopt = '-c 1 -W 1';
  } elsif ($uname eq 'IRIX') {	# SGI
    $ping = '/usr/etc/ping';
    $preopt = '-c 1 -w 1';
  }

  # Couldn't determine this system?  Assume all machines are dead!
  return 1 unless ($ping);

  # Run 'ping' and examine the results.
  if (open(PING, "$ping $preopt $sun $postopt|")) {
    while (<PING>) {
      if (/(\s0\s+(packets\s+)?received|no\s+answer\s+from)/) {
        # Found '0 packets received' or '0 received' or 'no answer from ...'
        close(PING);
        return ($num_processors{$sun} + 1);
      } elsif (/([0\.]+%\s+packet\s+loss|\s+is\s+alive)/) {
        # Found '0% packet loss' or '... is alive'
        close(PING);
        return 0;
      }
    }
  }
  close(PING);

  # Can't ping, must be dead!
  return ($num_processors{$sun} + 1);
}

sub usage {
  # Returns the usage string.
  my $usage = <<EOU;
Usage:	$0 fltnum startrev stoprev destination(optional)
Or	$0 fltnum startdate stopdate destination(optional)

Options:
	-n		Farm out jobs to machines on the network.  If not set,
			the default is to use only the local machine.

	-a machine	Add "machine" to the list of machines.

	-x machine	Exclude "machine" from the list of machines.

	-w wait		Wait 'wait' seconds after a machine fails to run a rev
			before trying that machine again.  Default: 900.

	-j n		Run only every 'n' revs.  Default 1 to run every rev.
			Ignored if start/stop are dates rather than revs.

	-k		Keep generated script files and exit status output
			(otherwise they are removed when finished)

	-s n		Minimum number of scans to run an RSDR file.  Files
			that are too small to contain this number of scans
			will be skipped (this determination is approximate).
			Default 0 means no minimum.
EOU

  return $usage;
}

sub interrupted {
  # Handle interrupt signals (such as Ctrl-C from the keyboard).  Child
  # processes won't catch these, so they'll perform the default action, which
  # is to exit immediately.  In the parent process, we'll truncate remaining
  # scan lists so the main loop finishes.

  @revlist = ();
  @revrsdr = ();
  %retry_rsdr = ();
  $finished = 1;
}
#################################################################
#!/bin/csh
#------------------------------------------------------------------------
# File : gps_setdir

#
# Figure out the absolute path of where we're installing...
#
set SCRIPT_DIR=`dirname .`
set DOTDIR=`echo $SCRIPT_DIR | cut -c1`
set CWD=`pwd`

if ( "$DOTDIR" == ".") then
  set USEDIR=${CWD}/${SCRIPT_DIR}
else
  set USEDIR=$CWD
endif

set USEDIR=`echo $USEDIR | sed -e 's/\/\/*/\//g'`
set USEDIR=`echo $USEDIR | sed -e 's/\/\.//g'`
set USEDIR=`echo $USEDIR | sed -e 's/\/CMDFILES$//'`

setenv GPS_DBDIR  "${USEDIR}/DATABASES/"
setenv GPS_DFDIR  "${USEDIR}/DATAFILES/"
setenv GPS_EXEDIR "${USEDIR}/EXECUTABLES/"
setenv GPS_IDIR   "${USEDIR}/INPUT/"
setenv GPS_ODIR   "${USEDIR}/OUTPUT/"
setenv GPS_SUMDIR "${USEDIR}/SUMMARY/"

if (! -d ${GPS_ODIR}) mkdir ${GPS_ODIR}
if (! -d ${GPS_IDIR}) mkdir ${GPS_IDIR}
if (! -d ${GPS_SUMDIR}) mkdir ${GPS_SUMDIR}

#############################################################
#automis.py
from sgp4.earth_gravity import wgs84
from sgp4.io import twoline2rv
from skyfield.api import load, EarthSatellite
from skyfield.framelib import itrs
from datetime import datetime, timezone
from datetime import timedelta
from urllib.request import urlopen, pathname2url
import sys, os
from skyfield.iokit import parse_tle_file
from io import BytesIO
from sgp4.api import Satrec
from sgp4.api import jday
from sgp4.api import days2mdhms
from sgp4.conveniences import sat_epoch_datetime
import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt
import datetime as dtt
from datetime import timedelta
from pyproj import CRS, Transformer
import math
import time
from urllib.parse import urljoin
import glob
import re
import math
import subprocess

sdir = os.path.dirname(os.path.abspath(__file__)) + "/data/"
tdir = os.path.dirname(os.path.abspath(__file__)) + "/geotestlog/"
maxnumrev = 6000

def haversine(lon1, lat1, lon2, lat2):
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    # Radius of earth in kilometers is 6371
    km = 6371*c
    return km

# get the circle distance between two points on the earth (unit in degrees)
def dist(lat1, long1, lat2, long2):
    # convert decimal degrees to radians 
    lat1, long1, lat2, long2 = map(radians, [lat1, long1, lat2, long2])
    # haversine formula 
    dlon = long2 - long1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    # Radius of earth in kilometers is 6371
    km = 6371* c
    return km

# find the distance of two geo locations
def find_dist(lat, lon, refdata):
    distances = refdata.apply(
        lambda row: dist(lat, lon, row['latitude(degree)'], row['longitude(degree)']), 
        axis=1)
    return refdata.loc[distances.idxmin(), 'name']

# Converts ECEF (x, y, z) coordinates to latitude, longitude, and altitude.
def xyz_to_lla(x, y, z, crs_in='EPSG:4978', crs_out='EPSG:4326'):
    transformer = Transformer.from_crs(crs_in, crs_out, always_xy=True)
    lon, lat, alt = transformer.transform(x, y, z)
    return lat, lon, alt

# get tle information
def get_tle(lines, n, key, zeroline, lst):
    i = 0
    sch=''
    while i < n:
        ll = lines[i]
        if key in ll: 
           ll0 = lines[i]
           ll1 = lines[i+1] 
           ll2 = lines[i+2]
           if(zeroline == 0):
              sch = ll.strip()+ '\n' + ll1.strip() + '\n' + ll2.strip()
              if lst == 1:
                  sch = sch.splitlines()
           else:
              sch = ll1.strip() + '\n' + ll2.strip()
              if lst == 1:
                  sch = sch.splitlines()
           i += 2
        i += 1
    return sch

def getnums(string):
     numstr = re.findall(r'\d+', string)
     intnum = [int(item) for item in numstr]
     return intnum

def findfiles(path, pat, keys):
    nofile = "skip"
    matchfiles = os.path.join(path, pat)
    pp = glob.glob(matchfiles)
    minn=9999999
    retl=''
    retf = ''   
    for index, item in enumerate(pp):
        ff = os.path.basename(pp[index])
        ll = getnums(ff)
        if abs(keys-ll[0]) < minn and abs(keys-ll[0]) < maxnumrev:
            minn = keys-ll[0]
            retf = ff
            retl = ll[0]
    return minn, retl, retf

def extract_number(f):
    s = re.findall("\\d+$",f)
    return (int(s[0]) if s else -1,f)

# get orbit information
def geo_info(sat, mtime, us_inc, num_samples, line1, line2, fname, deci, minn):

    output_filename = sat.strip() + "" + \
            mtime.strftime("%Y_%m_%d_%H_%M_%S_%f") \
            + ".csv"
    output_filename = output_filename.replace(" ", "_").replace("(", "_")\
            .replace(")", "_").replace("/", "_")\
            .replace("[", "_").replace("]", "_")
            
    outpath = tdir + output_filename
    
    outfile = open(outpath, "w")
    outfile.write("year, " + "month, "+ "day, " + "hour, " + "min, " + "sec, "+ "itlat, " + "itlon, " + "italt," + "rev#" + "\n");

    satellite = twoline2rv(line1, line2, wgs84)
    
    orbit_number = int(line2[63:63 + 5].strip())  # Get the orbit number.
    print(orbit_number)
    
    tss = load.timescale()
    filep = sdir + fname 
    if os.path.exists(filep):
        print(filep)
    else:
        print(f"File '{filep}' does not exist.")    
        return "skipped"
    with load.open(filep) as ff:
        skysatellites = list(parse_tle_file(ff, tss))
        
    if skysatellites:
        print(f"Loaded {len(skysatellites)} skysatellites.")
        print(f"First satellite: {skysatellites[0].name}")
    
    # Define a time for position calculation
    ttt = tss.utc(datetime.now(timezone.utc))
    
    # Access a satellite by name
    ssat = skysatellites[0]

    # Calculate position
    geocentric = ssat.at(ttt)

    epoch_year = line1[18:20].strip()
    tle_epoch_year = 2000 + int(epoch_year)
    tle_epoch_day = float(line1[20:32].strip())
    tle_epoch_datetime = datetime(tle_epoch_year, 1, 1) + timedelta(days=tle_epoch_day - 1)
    # Get the revolution number at the TLE epoch
    rev_at_epoch = int(line2[63:68].strip())
    mean_motion_str = line2[52:63].strip()
    mean_motion = float(mean_motion_str)
    print(mean_motion)

    mtime = mtime + timedelta(hours=(24/mean_motion)*(minn-1), minutes=0)
    
    for i in range(0, num_samples, deci):
        datestamp = mtime.strftime("%Y,%m,%d,%H,%M,%S.%f")
        target_time = datetime(mtime.year, mtime.month, mtime.day, \
                      mtime.hour, mtime.minute, mtime.second)        
        time_diff_days = (target_time - tle_epoch_datetime).total_seconds() \
		                  / (24 * 3600)
        rev_since_epoch = mean_motion * time_diff_days
        rev_t = rev_at_epoch + round(rev_since_epoch)
        if i == 0:
            revst = rev_t
        
        if i == (num_samples-1):
            reved = rev_t
               
        second = float(str(mtime.second) + "." + str(mtime.microsecond))
        position, v = satellite.propagate(mtime.year, mtime.month, mtime.day, \
                mtime.hour, mtime.minute, second)

        revnum = satellite.revnum
        tsss = tss.utc(mtime.year, mtime.month, mtime.day, mtime.hour, \
                       mtime.minute, mtime.second)
        geocentric = ssat.at(tsss)
        position_itrs = geocentric.frame_xyz(itrs).km    
        itlat, itlon, italt = xyz_to_lla(position_itrs[0]*1000, \
                              position_itrs[1]*1000, position_itrs[2]*1000)
        position_string = ","
        latitude, longitude, altitude = xyz_to_lla(position[0]*1000, \
                                        position[1]*1000, position[2]*1000)   
        position_string += " "
        position_string += str(itlat) + ","
        position_string += " "        
        position_string += str(itlon) + ","
        position_string += " "
        position_string += str(italt) + ","
        position_string += " "
        position_string += str(rev_t) 
        
        outfile.write(datestamp + position_string + "\n");
        mtime = mtime + timedelta(microseconds=us_inc)*deci
        reved = rev_t

    outfile.close()
    ff.close()
    dirname, basefile = os.path.split(outpath)
    newname = str(revst) + "-" + str(reved) + "-" + basefile
    if os.path.exists(os.path.join(dirname, newname)):
        os.remove(os.path.join(dirname, newname))
    os.rename(outpath, os.path.join(dirname, newname))
    retout = os.path.join(dirname, newname)
    print("retout ", retout)
    return retout
    
def misproc(file_path):
    noforbidden = True
    f16="DMSP 5D-3 F16"
    f17="DMSP 5D-3 F17"
    f18="DMSP 5D-3 F18"
    tle_stringf16 = []
    tle_stringf17 = []
    tle_stringf18 = []
    nzero = 0
    epochf = 0
    infile = 0
    line1 = ""
    line2 = ""
    nline = 0
    tle_fstring = [''] * 3
    tle_filename = ""
    altmis = True
    minn = 0
    satinfo = "skipped"
    fsize = 31000000 #file size in byte
    file_size = fsize
	
    if altmis:
        print(file_path)
        base = os.path.dirname(file_path)
        basename = os.path.basename(file_path)
        print(basename)
		##lc test
        file_size = os.path.getsize(file_path)
        tmpstr = (basename.split(".")[0])[3:] 
        numstr = re.search(r'\d+', tmpstr)
        retnum = numstr.group()		
        keys = int(retnum)
        print("keys:", keys)

        flt=basename[0:3]
        fpath = "./data"
        pat = "tle_"+"*"+flt+"*.csv" 
        base = os.path.dirname(os.path.abspath(__file__)) + "/data/"
        minn, retl, retf = findfiles(base, pat, keys)
        if minn == 9999999:
            print(keys, " skipped!")
            return satinfo
        else:
            print(minn, retl, retf, keys)

        file_url = "file:///" + (os.path.join(base, retf)).replace("\\", "/")
        html = urlopen(file_url)
        with urlopen(file_url) as response:
            lines_bytes = html.readlines()
            lines_str = [line.decode('utf-8') for line in lines_bytes]
            noforbidden = True

    print(noforbidden)
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(tdir, exist_ok=True)
    if noforbidden:
        if altmis:
            lens = len(lines_str)
            start_time = time.perf_counter() 

        if altmis:
            flt_string = [flt]
        else:
            flt_string = [f16, f17, f18]

        for i in range(len(flt_string)):
            flt_str = get_tle(lines_str, lens, flt_string[i], 0, 1)
            line2 = flt_str[2].strip()
            line1 = flt_str[1].strip()
            line0 = flt_str[0].strip()
            sat = line0
            tle_string = flt_str[0].strip()+ '\n' + flt_str[1].strip() + '\n' + flt_str[2].strip() 
            epoch_year = line1[18:20].strip()
            epoch_day = float(line1[20:32])
            epoch = np.datetime64(dtt.datetime.strptime(epoch_year, "%y") + \
                                  dtt.timedelta(days=epoch_day - 1), "us")
            rep = str.maketrans({":": "_", ".": "_", " ": "_"})
            epoch = str(epoch).translate(rep)
            satstr = (line0.strip()).replace(" ", "_").replace("(", "_")\
                .replace(")", "_").replace("/", "_")\
                .replace("[", "_").replace("]", "_")                          
        
            dltime = time.strftime("%Y-%m-%d %H:%M:%S")
            dltime = str(dltime).translate(rep)
            tle_filename = "tle_" + line2[63:68].strip() + "_" + satstr + str(epoch) + ".csv"
            tle_str = open(sdir + tle_filename, "w")
            tle_str.write(tle_string)     
            tle_str.close()   
            
            satellite2 = Satrec.twoline2rv(line1, line2)
            if(int(epochf) == 1):
                month, day, hour, minute, second = days2mdhms(satellite2.epochyr, satellite2.epochdays)
                start = str(20)+str(satellite2.epochyr)+' '+str(month)+' '+str(day)+' '+str(hour)+' '+ \
                    str(minute)+' '+str(second).split('.')[0]+' '+str(second).split('.')[1]
            else:
                month, day, hour, minute, second = days2mdhms(satellite2.epochyr, satellite2.epochdays)               
                start = str(20)+str(satellite2.epochyr)+' '+str(month)+' '+str(day)+' '+str(hour)+' '+ \
                    str(minute)+' '+str(second).split('.')[0]+' '+str(second).split('.')[1]
            
            inc = 1           
            us_inc = inc
            us_inc = us_inc * 1e6
            num_samples = int(24*60*60) #test only
            if altmis:
                if file_size > fsize:
                    num_samples = int(6*60*60)
                else:
                    num_samples = int(5*60*60)
        
            time2 = datetime.strptime(start.strip(), "%Y %m %d %H %M %S %f")
            tledl = False
            deci = 1
            if not tledl:    
                satinfo = geo_info(sat, time2, us_inc, num_samples, line1, line2, tle_filename, deci, minn)
            
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            print(f"Elapsed time: {elapsed_time:.6f} seconds")                     
           
    print ("done")
    print(satinfo)
    return satinfo

##############################################################
#misWatch.py
import os
import time
import taskRsdr as schr
import sys
import datetime
import argparse

test_flag = False
test_folder = "/2026/testonly/"
#test_folder = "2026/March/"
#test_folder = "2026/Feb/2026.02.28/"
#test_folder = "2026/test/"

if test_flag:
###   watchDogDir = ['/home/dmsp/dmspdata/Processed/MIS-DropBox/' + test_folder]
   watchDogDir = ['/mnt/scratch/2/dmsp/dmspdata/Processed/MIS-DropBox/' + test_folder]
   destDir = '/scratch/users/m26814/newrsdrfiles/' + test_folder
else:
###   watchDogDir = ['/home/dmsp/dmspdata/Processed/MIS-DropBox/'] 
   watchDogDir = ['/mnt/scratch/2/dmsp/dmspdata/Processed/MIS-DropBox/'] 
   destDir = '/scratch/users/m26814/newrsdrfiles/'

timeINT = 30 #interval time (seconds)
start_date = datetime.datetime.now()
timeout=10

fileList = False
file_list = []

date_format = '%Y%m%d'

def find_files(directory, file_extension=None):
    found_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(file_extension.upper()) or file.endswith(file_extension.lower()):
                create_time = os.stat(os.path.join(root, file)).st_mtime	

                if test_flag:
                   if fileList:
                      if file in file_list:
                         found_files.append(os.path.join(root, file))
                   else:
                      found_files.append(os.path.join(root, file))
                else:
                   if (start_date <= datetime.datetime.fromtimestamp(create_time)):
                      found_files.append(os.path.join(root, file)) 
              
    return found_files

def wait_until_ready(file_path):
	start_time = time.time()
	last_size = -1
	while time.time() - start_time < timeout:
		try:
			current_size = os.path.getsize(file_path)
			if current_size == last_size and current_size > 0:
				return True
			last_size = current_size
		except OSError:
			pass
		time.sleep(1)
	print(f"Timed out waiting for file: {file_path}")
	return False

def add_to_path(base_path, subdir_name):
    combined_path = os.path.join(base_path, subdir_name)
    return combined_path

#search dmsp data files
def checkNewDmspFile(processedDmspFiles, newDmspFileList):
    differencesList = [x for x in newDmspFileList if x not in processedDmspFiles]
    return(differencesList)

#process dmsp data files
def processNewDmspdata(newDmspFiles):
    for i in newDmspFiles:
       if not os.path.isfile(i):
          if wait_until_ready(i):
             print(i)
          else:
             continue

       schr.schTasks(i, destDir, watchDogDir)

#watchdog for new dmsp data files
def dmspDataWatcher(watchDir, timeINT):
    length = len(watchDir)
    processedDmspFiles = []
    startRunning = []
    newDmspFileList = []
    Diffs = []
    listDir = []
    for i in range(length):
       processedDmspFiles.append(0)
       startRunning.append(0)
       newDmspFileList.append(0)
       Diffs.append(0)
       listDir.append(0)

    while True:
       # Iterating the index
       for i in range(length):
           #starting running only
           if startRunning[i] == 0:
               processedDmspFiles[i] = []
               startRunning[i] = 1
           newDmspFileList[i] = find_files(watchDogDir[i], '.MIS')                                     	   
           Diffs[i] = checkNewDmspFile(processedDmspFiles[i], newDmspFileList[i])

           processedDmspFiles[i] = newDmspFileList[i]
           if len(Diffs[i]) == 0:
              continue
           processNewDmspdata(Diffs[i])
       if test_flag:
           sys.exit()
       else:
           time.sleep(timeINT)

#driver code
if __name__ == "__main__":
#main function to launch a watchdog for the upcoming new dmsp data
#Usage: python3 {sys.argv[0]} <start_date_time (example: "11/30/23 15:31:26")>
   # global start_date
   dateformat = "%m/%d/%y"
   timeformat = ("%H:%M:%S")   
   parser=argparse.ArgumentParser(description="argument parser")
   parser.add_argument("date_time", nargs='?',default="now",)
   args, unknown = parser.parse_known_args()
   
   isExist = os.path.exists(destDir)
   if not isExist:
      os.makedirs(destDir)

   if args.date_time=="now":
       print("now:", start_date)
   else:           
       dt_str = args.date_time       
       test_str = (dt_str.strip()).split()
       if len(test_str) == 2:
          try:
             validstr = bool(datetime.datetime.strptime(test_str[0], dateformat))
             validstr = bool(datetime.datetime.strptime(test_str[1], timeformat))
          except ValueError:
             validstr = False
             print('Usage: python3 misWatch.py "start_date_time" \
                  (example: "11/30/23 15:31:26")')
             sys.exit()
       else:   
          print('Usage: python3 misWatch.py "start_date_time"\
               (example: "11/30/23 15:31:26")')
          sys.exit()

       datetime_object = datetime.datetime.strptime(dt_str, '%m/%d/%y %H:%M:%S')
       start_date = datetime_object
       print(start_date)
   dmspDataWatcher(watchDogDir, timeINT)

   sys.exit()

#############################################################
#rsdrFile.py
import subprocess
import os
import sys
import glob
import re
from automis import misproc
import shlex
from pathlib import Path

def srcfile2ext(file_path):
    base_name, extension = os.path.splitext(file_path)
    new_extension = extension.lower()
    new_file_path = base_name + new_extension
    try:
        os.rename(file_path, new_file_path)
    except:
        print(f"error in file: {file_path}")

def get_base_name(filename):
    base_name, _ = os.path.splitext(filename)
    return re.sub(r'\s*\(\d+\)$', '', base_name)
	
def clean_and_increment_filename(directory, filename):
    if os.path.isdir(os.path.join(directory, filename)):
        return None
        
    name, ext = os.path.splitext(filename)
    
    base_name = get_base_name(name)
    escaped_var = re.escape(base_name)
    
    name = re.sub(r'[\s\-_]+', '_', name)
    
    match = re.search(fr'{base_name}.*?\((\d+)\)', name, re.IGNORECASE)
    if match:
        num = int(match.group(1))
    else:
        return None

    while True:
        new_filename = f"{base_name}_{num:02d}{ext}"
        full_new_path = os.path.join(directory, new_filename)
        
        if not os.path.exists(full_new_path) or new_filename == filename:
            return new_filename
        
        num += 1

def nextnonexistent(f):
    fnew = f
    root, ext = os.path.splitext(f)
    i = 0
    while os.path.exists(fnew):
        i += 1
        fnew = '%s_%i%s' % (root, i, ext)
    return fnew

def file_rename(target_directory, filename):
    new_name = clean_and_increment_filename(target_directory, filename)
    if new_name and new_name != filename:
       old_path = os.path.join(target_directory, filename)
       new_path = os.path.join(target_directory, new_name)
       print("old_path=", old_path)
       print("new_path=", new_path)
       try:
          os.rename(old_path, new_path)
          print(f"Renamed: '{filename}' -> '{new_name}'")
          return new_path
       except OSError as e:
          print(f"Failure: {e}")
		  
          return None

    return None

def has_numbers_in_brackets(s):
    return bool(re.search(r'\(\d+\)', s))

def findfiles(path, pat, keys):
    nofile = "skip"
    matchfiles = os.path.join(path, pat)
    pp = glob.glob(matchfiles)
    for index, item in enumerate(pp):
        ff = os.path.basename(pp[index])
        ll = getnums(ff)
        if (keys > ll[0]) and (keys < ll[1]):
            return ff
    return nofile

def get_subpath(full_path, base_path):
    try:
        relative_path = os.path.relpath(full_path, base_path)
        return relative_path
    except ValueError:
        return full_path

def getnums(string):
     return [int(x) for x in re.findall(r'\d+', string)]

#new dmsp data
def rsdrprocess(src, dest, indir):
    pp = get_subpath(src, indir[0])
    pp = os.path.dirname(pp) + "/"
    args = os.path.basename(src)
    if args.find('mis') != -1 or args.find('MIS') != -1:
       print("Contains given substring ")
	   
       print("dest1", dest)
       if pp != '/':
          print(pp)
          dest = os.path.join(dest, pp)
       print("dest2", dest)
	   
       isExist = os.path.exists(dest)
       if not isExist:
         os.makedirs(dest)

       src_file = src
       base, ext = os.path.splitext(src_file) 
       basename = os.path.basename(src_file)  
       fpath = "./data"
       rets = misproc(src_file)	   	   
	            
       s = os.path.splitext(args)[0]	   
       if "_" in s:
           s = s.replace("_", "-")
		      
       procfile = True
       if(has_numbers_in_brackets(src)):
           procfile = False
           print("src_file0=", src)
           targetdir, oldfile = os.path.split(src)
           newfile = file_rename(targetdir, oldfile)

           if newfile:
              src_file = newfile
              sb = os.path.basename(src_file)
              sfile = os.path.splitext(sb)[0]
              dest = dest + sfile[0:3]+"_" + sfile[3:len(sfile)]+ ".dat"
              procfile = True
           else:
              procfile = False
              print("newfile = ", newfile)           
       else:
           dest = dest + s[0:3]+"_" + s[3:len(s)]+ ".dat"
           print(dest)
	   
       if rets != "skipped" and procfile: 

           cmd = "idl -e " + "'" + "mis2rsdr" + "," + '"'+src_file + '"' +"," + \
                 '"'+dest + '"' +"," + '"'+ str(rets) + '"' +"'"
           os.system(cmd) 
           os.remove(str(rets))
		   
#driver of rsdr processing
if __name__ == '__main__':
    if len(sys.argv) > 2 : 
       rsdrprocess(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
       raise SystemExit(f"Usage: python3 {sys.argv[0]} <dmsp_data> \
                         <output_path> <indir_path>...")  
#################################################################
#taskRsdr.py
import subprocess
import os
import sys
import rsdrFile

#schedule a task
def schTasks(src, dest, indir):
    rsdrFile.rsdrprocess(src, dest, indir)

#driver
if __name__ == '__main__':

    if len(sys.argv) > 2 : 
       schTasks(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
       raise SystemExit(f"Usage: python3 {sys.argv[0]} \
                        <dmsp_data> <output_path> <indir_path>...")
########################################################################						
	

require 'fileutils'
TIME_STRING_MATCHER = /^\d+[dhms]?$/.freeze

class Sleeper
  def self.wait
    sleep 1
  end
end

def format_timer(total_seconds)
  seconds = (total_seconds % 60).to_i
  minutes = ((total_seconds / 60) % 60).to_i
  hours = (total_seconds / (60 * 60)).to_i
  time = format('%02ds', seconds)
  time = format('%02d:%02d', minutes, seconds) if minutes != 0 || hours != 0
  time = "#{hours}:#{time}" if hours != 0
  time.to_s
end

def seconds_from_string(time_string)
  name = ''
  run_seconds = 0
  time_string.split(' ').each do |digit|
    if digit.match(TIME_STRING_MATCHER)
      run_seconds += case digit
                     when /\d+d/
                       digit.sub('d', '').to_i * 86_400
                     when /\d+h/
                       digit.sub('h', '').to_i * 3600
                     when /\d+m/
                       digit.sub('m', '').to_i * 60
                     when /\d+s/
                       digit.sub('s', '').to_i
                     else
                       if run_seconds.zero?
                         digit.sub('s', '').to_i
                       else
                         name += "#{digit} "
                       end
                     end
    else
      name += "#{digit} "
    end
  end
  name = "#{time_string} timer" if name == ''
  [run_seconds, name.strip]
end

def set_timer(time_string)
  start_time = Time.now

  timer_file = "timer_#{rand(1..10_000)}.txt"
  timer_file = "timer_#{rand(1..10_000)}.txt" while File.exist?(timer_file)

  FileUtils.touch(timer_file)

  run_seconds, name = seconds_from_string(time_string)

  while Time.now < (start_time + run_seconds)
    Sleeper.wait
    return '' unless File.exist?(timer_file)

    File.write(timer_file, "#{format_timer(start_time - Time.now + run_seconds)}, #{name}")
  end

  FileUtils.rm(timer_file)

  "#{name} is done!"
end

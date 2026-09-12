% Buddy live productivity score plot
% Run this in MATLAB after the PC agent starts writing buddy_score.csv

CSV_PATH = fullfile(fileparts(mfilename('fullpath')), '..', 'buddy_score.csv');
API_URL  = 'http://127.0.0.1:8000/stats';

figure('Name','Buddy — Productivity Score','NumberTitle','off');

while true
    try
        % Saturday upgrade: pull from API
        data = webread(API_URL);
        if ~isempty(data)
            t = datetime({data.bucket}, 'InputFormat', 'yyyy-MM-dd''T''HH:mm:ss');
            s = [data.avg_score];
            clf;
            plot(t, s, 'b-o', 'LineWidth', 2);
            yline(35, '--r', 'Label', 'Slump threshold');
            ylim([0 100]);
            ylabel('Productivity score');
            xlabel('Time');
            title('Buddy — Live Score');
            grid on;
            drawnow;
            pause(5);
            continue;
        end
    catch
        % Fall back to CSV if API is not up yet
    end

    % CSV fallback
    if exist(CSV_PATH, 'file')
        try
            T = readtable(CSV_PATH);
            if height(T) > 0
                t = datetime(T.timestamp, 'InputFormat', 'yyyy-MM-dd''T''HH:mm:ss');
                s = T.score;
                clf;
                plot(t, s, 'b-', 'LineWidth', 2);
                yline(35, '--r', 'Label', 'Slump threshold');
                ylim([0 100]);
                ylabel('Productivity score');
                xlabel('Time');
                title('Buddy — Live Score (CSV)');
                grid on;
                drawnow;
            end
        catch e
            disp(['CSV read error: ' e.message]);
        end
    else
        title('Buddy — waiting for data...');
        drawnow;
    end

    pause(2);
end

from funasr import AutoModel
import soundfile
import io

class ASRServer:
    def __init__(self):
        self.vad_model = AutoModel(model="fsmn-vad", model_revision="v2.0.4")
        self.asr_model = AutoModel(model="paraformer-zh", model_revision="v2.0.4")
    
    def process_audio(self, audio_data):
        speech, sample_rate = soundfile.read(io.BytesIO(audio_data))
        chunk_size = 200  # ms
        chunk_stride = int(chunk_size * sample_rate / 1000)
        
        cache = {}
        results = []
        total_chunk_num = int(len(speech) / chunk_stride)
        for i in range(total_chunk_num):
            chunk = speech[i*chunk_stride:(i+1)*chunk_stride]
            is_final = i == total_chunk_num - 1
            vad_res = self.vad_model.generate(input=chunk, cache=cache, is_final=is_final, chunk_size=chunk_size)
            
            if len(vad_res[0]["value"]):
                asr_res = self.asr_model.generate(input=chunk)
                results.append(asr_res)
        
        return results

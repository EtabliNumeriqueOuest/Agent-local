import torch
import torch.nn as nn



class InputEmbedding(nn.Module):
    def __init__(self, dimension_model: int, vocabulary_size: int):
        super().__init__()
        self.dimension_model = dimension_model
        self.vocabulary_size = vocabulary_size
        self.embedding = nn.Embedding(vocabulary_size, dimension_model)

    def forward(self, x):
        x = self.embedding(x)
        return x * (self.dimension_model ** 0.5)



class PositionalEncoding(nn.Module):

    def __init__(self, dimension_model: int, maximum_sequence_length: int, dropout: float) -> None:
        super().__init__()
        self.dimension_model = dimension_model  # d_model
        self.maximum_sequence_length = maximum_sequence_length
        self.dropout = nn.Dropout(dropout)

        # Create a matrix of shape (maximum_sequence_length, dimension_model)
        positional_encoding = torch.zeros(maximum_sequence_length, dimension_model)

        # Create a vector of shape (maximum_sequence_length)
        position = torch.arange(0, maximum_sequence_length, dtype=torch.float).unsqueeze(1)
        denominator = torch.exp(torch.arange(0, dimension_model, 2).float() * -(torch.log(torch.tensor(10000.0)) / dimension_model))

        # Apply the sine and cosine functions
        positional_encoding[:, 0::2] = torch.sin(position * denominator)
        positional_encoding[:, 1::2] = torch.cos(position * denominator)

        positional_encoding = positional_encoding.unsqueeze(0)

        self.register_buffer('positional_encoding', positional_encoding)

    def forward(self, x):
        x = x + (self.positional_encoding[:, :x.shape[1], :]).requires_grad_(False)
        return self.dropout(x)



class LayerNormalisation(nn.Module):

    def __init__(self, epsilon: float = 10**-6) -> None:
        super().__init__()
        self.epsilon = epsilon
        # alpha and bias play the roles of gamma (scale) and beta (shift) in LayerNorm, but as one scalar each instead of one per feature
        self.alpha = nn.Parameter(torch.ones(1))  # Multiplicative factor
        self.bias = nn.Parameter(torch.zeros(1))  # Additive factor

    def forward(self, x):
        mean = x.mean(dim = -1, keepdim=True)
        std = x.std(-1, keepdim=True)
        return self.alpha * (x - mean) / (std + self.epsilon) + self.bias



class FeedForwardBlock(nn.Module):

    def __init__(self, dimension_model: int, dimension_feedforward: int, dropout: float) -> None:
        super().__init__()
        self.linear1 = nn.Linear(dimension_model, dimension_feedforward)  # W1 and b1
        self.dropout = nn.Dropout(dropout)
        self.linear2 = nn.Linear(dimension_feedforward, dimension_model)  # W2 and b2

    def forward(self, x):
        # (Batch, maximum_sequence_length, dimension_model)
        # --> (Batch, maximum_sequence_length, dimension_feedforward)
        # --> (Batch, maximum_sequence_length, dimension_model)
        return self.linear2(self.dropout(torch.relu(self.linear1(x))))



class MultiHeadAttentionBlock(nn.Module):

    def __init__(self, dimension_model: int, number_of_heads: int, dropout: float) -> None:
        super().__init__()
        self.dimension_model = dimension_model  # d_model
        self.number_of_heads = number_of_heads  # h
        assert dimension_model % number_of_heads == 0, "dimension_model must be divisible by number_of_heads"
        self.dimension_head = dimension_model // number_of_heads  # d_k

        self.w_q = nn.Linear(dimension_model, dimension_model)  # Wq
        self.w_k = nn.Linear(dimension_model, dimension_model)  # Wk
        self.w_v = nn.Linear(dimension_model, dimension_model)  # Wv

        self.w_o = nn.Linear(dimension_model, dimension_model)  # Wo
        self.dropout = nn.Dropout(dropout)

    @staticmethod
    def attention(query, key, value, mask, dropout: nn.Dropout):
        dimension_head = query.shape[-1]  # d_k

        # (Batch, number_of_heads, maximum_sequence_length, dimension_head)
        # --> (Batch, number_of_heads, maximum_sequence_length, maximum_sequence_length)
        attention_scores = torch.matmul(query, key.transpose(-2, -1)) / (dimension_head ** 0.5)
        if mask is not None:
            attention_scores = attention_scores.masked_fill(mask == 0, float('-inf'))
        attention_scores = torch.softmax(attention_scores, dim=-1)

        if dropout is not None:
            attention_scores = dropout(attention_scores)
        
        return torch.matmul(attention_scores, value), attention_scores

    def forward(self, q, k, v, mask):
        query = self.w_q(q)  # (Batch, maximum_sequence_length, dimension_model) --> (Batch, maximum_sequence_length, dimension_model)
        key = self.w_k(k)    # (Batch, maximum_sequence_length, dimension_model) --> (Batch, maximum_sequence_length, dimension_model)
        value = self.w_v(v)  # (Batch, maximum_sequence_length, dimension_model) --> (Batch, maximum_sequence_length, dimension_model)

        # (Batch, maximum_sequence_length, dimension_model)
        # --> (Batch, maximum_sequence_length, number_of_heads, dimension_head)
        # --> (Batch, number_of_heads, maximum_sequence_length, dimension_head)
        query = query.view(query.shape[0], query.shape[1], self.number_of_heads, self.dimension_head).transpose(1, 2)
        key = key.view(key.shape[0], key.shape[1], self.number_of_heads, self.dimension_head).transpose(1, 2)
        value = value.view(value.shape[0], value.shape[1], self.number_of_heads, self.dimension_head).transpose(1, 2)

        x, self.attention_scores = self.attention(query, key, value, mask, self.dropout)

        # (Batch, number_of_heads, maximum_sequence_length, dimension_head)
        # --> (Batch, maximum_sequence_length, number_of_heads, dimension_head)
        # --> (Batch, maximum_sequence_length, dimension_model)
        x = x.transpose(1, 2).contiguous().view(x.shape[0], -1, self.number_of_heads * self.dimension_head)

        # (Batch, maximum_sequence_length, dimension_model)
        # --> (Batch, maximum_sequence_length, dimension_model)
        return self.w_o(x)



class ResidualConnection(nn.Module):

    def __init__(self, dropout: float) -> None:
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        self.norm = LayerNormalisation()

    def forward(self, x, sublayer):
        return x + self.dropout(sublayer(self.norm(x)))



class EncoderBlock(nn.Module):

    def __init__(self, self_attention_block: MultiHeadAttentionBlock, feed_forward_block: FeedForwardBlock, dropout: float) -> None:
        super().__init__()
        self.self_attention_block = self_attention_block
        self.feed_forward_block = feed_forward_block
        self.residual_connections = nn.ModuleList([ResidualConnection(dropout) for _ in range(2)])

    def forward(self, x, source_mask):
        x = self.residual_connections[0](x, lambda x: self.self_attention_block(x, x, x, source_mask))
        x = self.residual_connections[1](x, self.feed_forward_block)
        return x



class Encoder(nn.Module):

    def __init__(self, layers: nn.ModuleList) -> None:
        super().__init__()
        self.layers = layers
        self.layer_norm = LayerNormalisation()

    def forward(self, x, source_mask):
        for layer in self.layers:
            x = layer(x, source_mask)
        return self.layer_norm(x)



class DecoderBlock(nn.Module):

    def __init__(self, self_attention_block: MultiHeadAttentionBlock, cross_attention_block: MultiHeadAttentionBlock, feed_forward_block: FeedForwardBlock, dropout: float) -> None:
        super().__init__()
        self.self_attention_block = self_attention_block
        self.cross_attention_block = cross_attention_block
        self.feed_forward_block = feed_forward_block
        self.residual_connections = nn.ModuleList([ResidualConnection(dropout) for _ in range(3)])

    def forward(self, x, encoder_output, source_mask, target_mask):
        x = self.residual_connections[0](x, lambda x: self.self_attention_block(x, x, x, target_mask))
        x = self.residual_connections[1](x, lambda x: self.cross_attention_block(x, encoder_output, encoder_output, source_mask))
        x = self.residual_connections[2](x, self.feed_forward_block)
        return x



class Decoder(nn.Module):

    def __init__(self, layers: nn.ModuleList) -> None:
        super().__init__()
        self.layers = layers
        self.layer_norm = LayerNormalisation()

    def forward(self, x, encoder_output, source_mask, target_mask):
        for layer in self.layers:
            x = layer(x, encoder_output, source_mask, target_mask)
        return self.layer_norm(x)



class ProjectionLayer(nn.Module):

    def __init__(self, dimension_model: int, vocabulary_size: int) -> None:
        super().__init__()
        self.projection_layer = nn.Linear(dimension_model, vocabulary_size)

    def forward(self, x):
        # (Batch, maximum_sequence_length, dimension_model)
        # --> (Batch, maximum_sequence_length, vocabulary_size)
        return torch.log_softmax(self.projection_layer(x), dim = -1)



class Transformer(nn.Module):

    def __init__(
            self,
            encoder: Encoder,
            decoder: Decoder,
            source_embedding: InputEmbedding,
            target_embedding: InputEmbedding,
            source_positional_encoding: PositionalEncoding,
            target_positional_encoding: PositionalEncoding,
            projection_layer: ProjectionLayer
        ) -> None:
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder
        self.source_embedding = source_embedding
        self.target_embedding = target_embedding
        self.source_positional_encoding = source_positional_encoding
        self.target_positional_encoding = target_positional_encoding
        self.projection_layer = projection_layer

    def encode(self, source, source_mask):
        source = self.source_embedding(source)
        source = self.source_positional_encoding(source)
        return self.encoder(source, source_mask)
    
    def decode(self, encoder_output, source_mask, target, target_mask):
        target = self.target_embedding(target)
        target = self.target_positional_encoding(target)
        return self.decoder(target, encoder_output, source_mask, target_mask)
    
    def project(self, x):
        return self.projection_layer(x)



def build_transformer(
        source_vocabulary_size: int,
        target_vocabulary_size: int,
        source_sequence_length: int,
        target_sequence_length: int,
        dimension_model: int = 512,
        Number_of_layers: int = 6,  # N for Encoder and Decoder
        number_of_heads: int = 8,   # h
        dropout: float = 0.1,
        dimension_feedforward: int = 2048  # d_ff
    ):

    # Create the embedding layers
    source_embedding = InputEmbedding(dimension_model, source_vocabulary_size)
    target_embedding = InputEmbedding(dimension_model, target_vocabulary_size)

    # Create the positional encoding layers
    source_positional_encoding = PositionalEncoding(dimension_model, source_sequence_length, dropout)
    target_positional_encoding = PositionalEncoding(dimension_model, target_sequence_length, dropout)

    # Create the encoder blocks
    encoder_blocks = []
    for _ in range(Number_of_layers):
        encoder_self_attention_block = MultiHeadAttentionBlock(dimension_model, number_of_heads, dropout)
        feed_forward_block = FeedForwardBlock(dimension_model, dimension_feedforward, dropout)
        encoder_block = EncoderBlock(encoder_self_attention_block, feed_forward_block, dropout)
        encoder_blocks.append(encoder_block)

    # Create the decoder blocks
    decoder_blocks = []
    for _ in range(Number_of_layers):
        decoder_self_attention_block = MultiHeadAttentionBlock(dimension_model, number_of_heads, dropout)
        decoder_cross_attention_block = MultiHeadAttentionBlock(dimension_model, number_of_heads, dropout)
        feed_forward_block = FeedForwardBlock(dimension_model, dimension_feedforward, dropout)
        decoder_block = DecoderBlock(decoder_self_attention_block, decoder_cross_attention_block, feed_forward_block, dropout)
        decoder_blocks.append(decoder_block)

    # Create the encoder and decoder
    encoder = Encoder(nn.ModuleList(encoder_blocks))
    decoder = Decoder(nn.ModuleList(decoder_blocks))

    # Create the projection layer
    projection_layer = ProjectionLayer(dimension_model, target_vocabulary_size)

    # Create the transformer model
    transformer = Transformer(
        encoder,
        decoder,
        source_embedding,
        target_embedding,
        source_positional_encoding,
        target_positional_encoding,
        projection_layer
    )

    # Initialize the parameters
    # dim() > 1 leaves out every bias and the LayerNorm alpha/bias scalars; those keep their constructor init (ones/zeros for LayerNorm)
    for p in transformer.parameters():
        if p.dim() > 1:
            nn.init.xavier_uniform_(p)

    return transformer